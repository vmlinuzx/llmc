"""
PHI filtering and redaction tools.

This module provides classes for detecting and handling Protected Health Information
through redaction, date shifting, and name surrogate generation.
"""

from datetime import datetime, timedelta
import hashlib

from .detector import PHIDetector


class DateShifter:
    """Consistently shifts dates for a given patient identifier.

    Uses a hash-based offset to ensure the same patient always gets the same
    date shift, preserving intervals between dates.
    """

    def __init__(self, patient_id: str, base_offset_days: int = 365):
        """Initialize a DateShifter for a specific patient.

        Args:
            patient_id: Unique identifier for the patient.
            base_offset_days: Base number of days to shift (default: 365).
                              The actual offset is derived from patient_id.
        """
        self.patient_id = patient_id
        self.base_offset_days = base_offset_days

        # Generate a deterministic offset from the patient_id
        hash_obj = hashlib.md5(patient_id.encode())
        hash_int = int(hash_obj.hexdigest(), 16)
        # Offset between -base_offset_days and +base_offset_days
        self.offset_days = (hash_int % (2 * base_offset_days)) - base_offset_days

        # Cache shifted dates to ensure consistency
        self.date_cache: dict[str, str] = {}

    def shift_date(self, date_str: str, date_format: str = "%m/%d/%Y") -> str:
        """Shift a date string by the patient's offset.

        Args:
            date_str: The original date string.
            date_format: Format of the input date string.

        Returns:
            Shifted date string in the same format.
        """
        # Check cache first
        cache_key = f"{date_str}|{date_format}"
        if cache_key in self.date_cache:
            return self.date_cache[cache_key]

        try:
            # Parse the date
            original_date = datetime.strptime(date_str, date_format)
            # Apply offset
            shifted_date = original_date + timedelta(days=self.offset_days)
            # Format back to string
            shifted_str = shifted_date.strftime(date_format)

            # Cache and return
            self.date_cache[cache_key] = shifted_str
            return shifted_str
        except ValueError:
            # If parsing fails, return the original string
            return date_str


class NameSurrogate:
    """Maps names to consistent placeholders like [NAME_1], [NAME_2], etc.

    Maintains a mapping from original names to surrogate placeholders,
    ensuring the same name always maps to the same placeholder within a session.
    """

    def __init__(self):
        """Initialize an empty name mapping."""
        self.name_to_surrogate: dict[str, str] = {}
        self.surrogate_counter = 1

    def get_surrogate(self, name: str) -> str:
        """Get or create a surrogate placeholder for a given name.

        Args:
            name: The original name.

        Returns:
            A surrogate placeholder like [NAME_1], [NAME_2], etc.
        """
        # Normalize the name: trim and title case
        normalized = name.strip().title()

        if normalized in self.name_to_surrogate:
            return self.name_to_surrogate[normalized]

        # Create a new surrogate
        surrogate = f"[NAME_{self.surrogate_counter}]"
        self.name_to_surrogate[normalized] = surrogate
        self.surrogate_counter += 1

        return surrogate

    def get_mapping(self) -> dict[str, str]:
        """Return the current name-to-surrogate mapping."""
        return self.name_to_surrogate.copy()


class PHIFilter:
    """Main class for PHI detection and filtering.

    Combines detection, date shifting, and name surrogate generation
    to redact or transform PHI in text.
    """

    def __init__(self, patient_id: str | None = None):
        """Initialize the PHI filter.

        Args:
            patient_id: Optional patient identifier for date shifting.
                        If None, dates will be redacted instead of shifted.
        """
        self.detector = PHIDetector()
        self.date_shifter = DateShifter(patient_id) if patient_id else None
        self.name_surrogate = NameSurrogate()

    def filter_text(
        self,
        text: str,
        redact_types: list[str] | None = None,
        shift_dates: bool = True,
        surrogate_names: bool = True,
    ) -> str:
        """Apply PHI filtering to the input text.

        Args:
            text: The input text containing potential PHI.
            redact_types: List of PHI types to redact completely (replace with [REDACTED]).
                          If None, all detected PHI will be processed according to other flags.
            shift_dates: Whether to shift dates (if patient_id was provided) or redact them.
            surrogate_names: Whether to replace names with surrogates or redact them.

        Returns:
            Filtered text with PHI handled according to the specified options.
        """
        if redact_types is None:
            redact_types = []

        # Get all PHI matches
        matches = self.detector.detect_with_text(text)

        # Sort matches by start position in reverse order to avoid index issues
        # when replacing text
        matches.sort(key=lambda m: m.start, reverse=True)

        result = text

        for match in matches:
            start, end, type_, original = match.start, match.end, match.type, match.text

            replacement = None

            if type_ in redact_types:
                replacement = "[REDACTED]"
            elif type_ == "DATE" and shift_dates and self.date_shifter:
                # Try common date formats
                for date_format in ["%m/%d/%Y", "%Y/%m/%d", "%m-%d-%Y", "%Y-%m-%d"]:
                    try:
                        datetime.strptime(original, date_format)
                        replacement = self.date_shifter.shift_date(
                            original, date_format
                        )
                        break
                    except ValueError:
                        continue
                if replacement is None:
                    replacement = "[REDACTED_DATE]"
            elif type_ == "NAME" and surrogate_names:
                replacement = self.name_surrogate.get_surrogate(original)
            else:
                # Default redaction for other types
                replacement = f"[REDACTED_{type_}]"

            # Replace the matched text
            result = result[:start] + replacement + result[end:]

        return result

    def redact_all(self, text: str) -> str:
        """Convenience method to redact all detected PHI.

        Args:
            text: Input text.

        Returns:
            Text with all PHI replaced by [REDACTED].
        """
        return self.filter_text(
            text, redact_types=["SSN", "PHONE", "EMAIL", "DATE", "MRN", "IP", "NAME"]
        )
