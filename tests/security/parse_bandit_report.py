import json


def parse_bandit_report(report_path):
    with open(report_path) as f:
        report = json.load(f)

    findings = []
    for result in report["results"]:
        findings.append(
            {
                "filename": result["filename"],
                "line_number": result["line_number"],
                "issue_text": result["issue_text"],
                "severity": result["issue_severity"],
                "confidence": result["issue_confidence"],
                "test_id": result["test_id"],
            }
        )
    return findings


if __name__ == "__main__":
    report_path = "tests/REPORTS/current/bandit_report.json"
    findings = parse_bandit_report(report_path)

    # Sort by severity and confidence
    sorted_findings = sorted(
        findings, key=lambda x: (x["severity"], x["confidence"]), reverse=True
    )

    for finding in sorted_findings:
        if finding["severity"] in ["HIGH", "MEDIUM"]:
            print(f"File: {finding['filename']}:{finding['line_number']}")
            print(f"  Issue: {finding['issue_text']}")
            print(f"  Severity: {finding['severity']}")
            print(f"  Confidence: {finding['confidence']}")
            print(f"  Test ID: {finding['test_id']}")
            print("-" * 20)
