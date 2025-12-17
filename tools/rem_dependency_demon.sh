#!/bin/bash

# Dependency Demon - CVE & Outdated Package Scanner

# Default to current directory if LLMC_ROOT is not set
REPO_ROOT="${LLMC_ROOT:-$(pwd)}"
cd "$REPO_ROOT" || exit 1

echo "Dependency Demon starting..."
echo "Target Repo: $REPO_ROOT"

# Check for pip-audit
if ! command -v pip-audit &> /dev/null; then
    echo "Error: pip-audit is not installed. Please run 'pip install pip-audit'"
    exit 1
fi

echo "---------------------------------------------------"
echo "1. Running pip-audit (OSV)..."

AUDIT_JSON=$(mktemp)
# Use -s osv for better severity data
pip-audit --progress-spinner off -s osv -f json -o "$AUDIT_JSON" > /dev/null 2>&1

# Python script to parse audit and drift
cat << 'EOF' > .demon_logic.py
import sys, json, os
from importlib.metadata import distributions

def check_audit(json_file):
    try:
        with open(json_file) as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading audit data: {e}")
        return 0

    critical_count = 0
    found_any = False

    print(f"{'Package':<20} {'Version':<15} {'ID':<20} {'Severity':<10}")
    print('-' * 70)

    for dep in data.get('dependencies', []):
        for vuln in dep.get('vulns', []):
            found_any = True
            severity_str = "UNKNOWN"
            is_critical = False

            # Try to extract severity from OSV data
            # 1. Check 'database_specific' (common in PyPI/OSV results from pip-audit)
            db_spec = vuln.get('database_specific')
            if db_spec and isinstance(db_spec, dict):
                if 'severity' in db_spec:
                    severity_str = str(db_spec['severity']).upper()

            # 2. Check top-level 'severity' field (list of vectors in OSV)
            # e.g., [{'type': 'CVSS_V3', 'score': 'CVSS:3.1/...'}]
            # We can't easily parse score, but we rely on database_specific often present.

            # Determine if CRITICAL
            if 'CRITICAL' in severity_str:
                is_critical = True

            print(f"{dep['name']:<20} {dep['version']:<15} {vuln['id']:<20} {severity_str:<10}")

            if is_critical:
                critical_count += 1

    if not found_any:
        print("No vulnerabilities found.")

    return critical_count

def check_drift():
    if not os.path.exists("requirements.txt"):
        print("requirements.txt not found.")
        return

    print("requirements.txt found. Checking against installed packages...")

    try:
        from pip_requirements_parser import RequirementsFile
    except ImportError:
        print("pip-requirements-parser module not found. Falling back to naive check.")
        return

    try:
        rf = RequirementsFile.from_file("requirements.txt")
        # Get installed packages (normalized names)
        installed = {d.metadata['Name'].lower(): d.version for d in distributions()}

        drift_found = False
        for req in rf.requirements:
             if not req.name: continue
             name = req.name.lower()

             if name not in installed:
                 print(f"  [MISSING] {req.name} (in requirements.txt but not installed)")
                 drift_found = True
             else:
                 pass

        if not drift_found:
             print("  All requirements present in environment.")

    except Exception as e:
        print(f"  Error parsing requirements.txt: {e}")

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "audit":
        sys.exit(check_audit(sys.argv[2]))
    elif mode == "drift":
        check_drift()
EOF

python3 .demon_logic.py audit "$AUDIT_JSON"
EXIT_CODE=$?

echo "---------------------------------------------------"
echo "2. Checking for Outdated Packages..."
pip list --outdated

echo "---------------------------------------------------"
echo "3. License Compliance..."
if command -v pip-licenses &> /dev/null; then
    pip-licenses
else
    echo "Skipping (pip-licenses not required/installed)"
fi

echo "---------------------------------------------------"
echo "4. Checking requirements.txt drift..."
python3 .demon_logic.py drift

# Cleanup
rm "$AUDIT_JSON" .demon_logic.py

exit $EXIT_CODE
