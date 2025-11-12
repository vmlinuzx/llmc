from __future__ import annotations

import argparse
import json
import re
import sys
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

EXEC_ROOT = Path(os.environ.get("LLMC_EXEC_ROOT") or Path(__file__).resolve().parents[2])
REPO_ROOT = Path(os.environ.get("LLMC_TARGET_REPO") or os.environ.get("LLMC_REPO_ROOT") or EXEC_ROOT)
LOGS_DIR = Path(os.environ.get("LLMC_DEEP_RESEARCH_LOG_DIR") or (REPO_ROOT / "logs"))
LOGS_DIR.mkdir(parents=True, exist_ok=True)
EVENT_LOG_PATH = LOGS_DIR / "deep_research.log"
USAGE_LOG_PATH = LOGS_DIR / "deep_research_usage.jsonl"
CONFIG_PATH = Path(os.environ.get("LLMC_DEEP_RESEARCH_CONFIG") or (EXEC_ROOT / "config" / "deep_research_services.json"))


DEFAULT_SERVICES = [
    {
        "id": "manual_service_a",
        "name": "Manual Deep Research A",
        "daily_quota": 500,
        "url": "",
        "notes": "Browser-based deep research slot",
    },
    {
        "id": "manual_service_b",
        "name": "Manual Deep Research B",
        "daily_quota": 300,
        "url": "",
        "notes": "Secondary provider",
    },
]


HIGH_RISK_KEYWORDS = {
    "architecture": 1.0,
    "architectural": 1.0,
    "system design": 1.2,
    "design doc": 1.3,
    "sdd": 1.3,
    "roadmap": 1.0,
    "migration": 1.1,
    "refactor": 1.0,
    "multi-service": 1.0,
    "monolith": 0.8,
    "compliance": 1.2,
    "hipaa": 1.4,
    "soc 2": 1.2,
    "pci": 1.2,
    "gdpr": 1.2,
    "security": 1.0,
    "threat": 1.1,
    "incident": 1.0,
    "postmortem": 1.2,
    "root cause": 1.0,
    "sla": 0.9,
    "slo": 0.9,
    "benchmark": 0.9,
    "load test": 1.0,
    "throughput": 0.9,
    "latency": 0.9,
    "capacity plan": 1.0,
    "regression": 0.7,
    "performance": 0.7,
    "compliance": 1.1,
    "legal": 1.1,
    "contract": 0.8,
    "governance": 1.0,
    "rollback": 0.9,
    "prod incident": 1.1,
    "runbook": 0.8,
    "disaster": 1.2,
    "backup": 0.7,
    "observability": 0.8,
    "telemetry": 0.7,
    "spec": 0.8,
    "requirements": 0.7,
    "analysis": 0.6,
    "evaluate": 0.6,
    "research": 0.8,
}


INTENT_PATTERNS: List[Tuple[re.Pattern[str], float, str]] = [
    (re.compile(r"\bdeep research\b", re.IGNORECASE), 1.5, "Explicit deep research request"),
    (re.compile(r"\bcomparative (study|analysis)\b", re.IGNORECASE), 1.2, "Comparative analysis"),
    (re.compile(r"\btrade[- ]?off", re.IGNORECASE), 1.0, "Trade-off analysis"),
    (re.compile(r"\bplan\b", re.IGNORECASE), 0.6, "Planning keyword detected"),
    (re.compile(r"\bproposal\b", re.IGNORECASE), 0.8, "Proposal requested"),
    (re.compile(r"\bstrategy\b", re.IGNORECASE), 0.8, "Strategy discussion"),
    (re.compile(r"\broadmap\b", re.IGNORECASE), 1.0, "Roadmap alignment"),
    (re.compile(r"\bregulat(ion|ory)\b", re.IGNORECASE), 1.2, "Regulatory consideration"),
    (re.compile(r"\bsecurity (assessment|review)\b", re.IGNORECASE), 1.4, "Security review requested"),
    (re.compile(r"\bgovernance\b", re.IGNORECASE), 1.0, "Governance topic"),
]


TOKEN_ESTIMATE_DIVISOR = 4
TOKEN_THRESHOLD = 900
CHAR_THRESHOLD = 3600


@dataclass
class DetectionResult:
    needs_deep_research: bool
    score: float
    confidence: float
    reasons: List[str]
    matched_keywords: List[str]
    token_estimate: int
    service_suggestions: List[Dict[str, object]]

    def to_dict(self) -> Dict[str, object]:
        return {
            "needs_deep_research": self.needs_deep_research,
            "score": round(self.score, 3),
            "confidence": round(self.confidence, 3),
            "reasons": self.reasons,
            "matched_keywords": self.matched_keywords,
            "token_estimate": self.token_estimate,
            "services": self.service_suggestions,
        }


def load_services() -> List[Dict[str, object]]:
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            services = data.get("services") if isinstance(data, dict) else None
            if isinstance(services, list) and services:
                normalized: List[Dict[str, object]] = []
                for idx, svc in enumerate(services):
                    if not isinstance(svc, dict):
                        continue
                    service_id = str(svc.get("id") or f"manual_service_{idx}").strip()
                    name = str(svc.get("name") or service_id).strip()
                    daily_quota = svc.get("daily_quota")
                    try:
                        daily_quota = int(daily_quota) if daily_quota is not None else None
                    except Exception:
                        daily_quota = None
                    normalized.append(
                        {
                            "id": service_id or f"manual_service_{idx}",
                            "name": name or f"Manual Deep Research {idx + 1}",
                            "daily_quota": daily_quota,
                            "url": str(svc.get("url") or "").strip(),
                            "notes": str(svc.get("notes") or "").strip(),
                        }
                    )
                if normalized:
                    return normalized
        except Exception:
            pass
    return DEFAULT_SERVICES.copy()


def read_usage_today(service_id: str, today: str) -> int:
    if not USAGE_LOG_PATH.exists():
        return 0
    used = 0
    try:
        with USAGE_LOG_PATH.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("service") == service_id and rec.get("date") == today:
                    used += 1
    except Exception:
        return 0
    return used


def log_usage(service_ids: Iterable[str], today: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        with USAGE_LOG_PATH.open("a", encoding="utf-8") as handle:
            for service_id in service_ids:
                record = {"timestamp": timestamp, "date": today, "service": service_id, "event": "suggested"}
                handle.write(json.dumps(record, ensure_ascii=False))
                handle.write("\n")
    except Exception:
        pass


def log_event(result: DetectionResult, prompt_excerpt: str) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "NEEDS_DEEP_RESEARCH" if result.needs_deep_research else "NO_DEEP_RESEARCH",
        "score": result.score,
        "confidence": result.confidence,
        "reasons": result.reasons,
        "matched_keywords": result.matched_keywords,
        "token_estimate": result.token_estimate,
        "excerpt": prompt_excerpt,
    }
    try:
        with EVENT_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")
    except Exception:
        pass


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // TOKEN_ESTIMATE_DIVISOR)


def detect(prompt: str) -> DetectionResult:
    text = prompt or ""
    lowered = text.lower()
    reasons: List[str] = []
    matched: Dict[str, float] = {}

    token_estimate = estimate_tokens(text)
    if token_estimate >= TOKEN_THRESHOLD:
        reasons.append(f"Long request (~{token_estimate} tokens)")
        matched["length"] = 1.0
    elif len(text) >= CHAR_THRESHOLD:
        reasons.append(f"Long request (~{len(text)} chars)")
        matched["length"] = 0.8

    for keyword, weight in HIGH_RISK_KEYWORDS.items():
        if keyword in lowered:
            reasons.append(f"Keyword match: {keyword}")
            matched[keyword] = max(matched.get(keyword, 0.0), weight)

    for pattern, weight, description in INTENT_PATTERNS:
        if pattern.search(text):
            reasons.append(description)
            matched[description] = max(matched.get(description, 0.0), weight)

    unique_reasons = []
    seen = set()
    for reason in reasons:
        if reason not in seen:
            unique_reasons.append(reason)
            seen.add(reason)

    total_score = sum(weight for weight in matched.values())
    needs_deep_research = total_score >= 2.0 or ("Explicit deep research request" in unique_reasons)
    confidence = min(1.0, total_score / 4.0) if needs_deep_research else min(0.6, total_score / 4.0)

    services = prepare_service_suggestions()
    matched_keywords = sorted(k for k in matched.keys() if k not in {"length"})

    result = DetectionResult(
        needs_deep_research=needs_deep_research,
        score=total_score,
        confidence=confidence,
        reasons=unique_reasons,
        matched_keywords=matched_keywords,
        token_estimate=token_estimate,
        service_suggestions=services,
    )

    excerpt = text.strip().splitlines()
    excerpt = "\n".join(excerpt[:3])
    log_event(result, excerpt)
    if needs_deep_research:
        today = datetime.now(timezone.utc).date().isoformat()
        log_usage([svc["id"] for svc in services], today)

    return result


def prepare_service_suggestions() -> List[Dict[str, object]]:
    today = datetime.now(timezone.utc).date().isoformat()
    services = load_services()
    suggestions: List[Dict[str, object]] = []
    for svc in services:
        service_id = svc["id"]
        used = read_usage_today(service_id, today)
        quota = svc.get("daily_quota")
        remaining = None
        if isinstance(quota, int):
            remaining = max(quota - used, 0)
        suggestions.append(
            {
                "id": service_id,
                "name": svc.get("name"),
                "daily_quota": quota,
                "used_today": used,
                "remaining_today": remaining,
                "url": svc.get("url") or "",
                "notes": svc.get("notes") or "",
            }
        )
    return suggestions


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Detect deep-research-worthy prompts.")
    parser.add_argument("--prompt", help="Prompt text to analyze.")
    parser.add_argument("--prompt-file", help="Path to a text file containing the prompt.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args(argv)

    prompt = args.prompt or ""
    if args.prompt_file:
        path = Path(args.prompt_file)
        if not path.exists():
            parser.error(f"Prompt file not found: {path}")
        prompt = path.read_text(encoding="utf-8")
    if not prompt:
        parser.error("No prompt provided.")

    result = detect(prompt)
    data = result.to_dict()
    if args.pretty:
        json.dump(data, sys.stdout, ensure_ascii=False, indent=2)
    else:
        json.dump(data, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
