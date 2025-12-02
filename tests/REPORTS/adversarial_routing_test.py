#!/usr/bin/env python3
"""
Adversarial testing of the routing system - attempting to break it with extreme inputs
"""

import sys

sys.path.insert(0, '/home/vmlinux/src/llmc')


from tests.test_routing_comprehensive import classify_query


def test_adversarial_inputs():
    """Test with extreme, weird, and malicious inputs."""

    test_cases = [
        # Empty and whitespace
        ("", "Empty query"),
        ("   ", "Only whitespace"),
        ("\n\n\n", "Only newlines"),
        ("\t\t\t", "Only tabs"),

        # Unicode and weird characters
        ("🎨 What color is the code? 🎨", "Emojis in query"),
        ("你好代码 你好", "Chinese characters"),
        ("Тест запроса", "Cyrillic"),
        ("🔥" * 100, "100 emojis"),
        ("Ω≈ç√∫˜µ≤≥÷", "Greek and math symbols"),
        ("\x00\x01\x02", "Null bytes"),

        # Extremely long inputs
        ("A" * 10000, "10k character query"),
        ("def func():\n    pass\n" * 1000, "1000 lines of code"),

        # SQL injection attempts
        ("'; DROP TABLE users; --", "SQL injection attempt"),
        ("' OR '1'='1", "SQL injection OR"),
        ("1; DELETE FROM config WHERE 1=1", "SQL DELETE attempt"),

        # Script injection attempts
        ("<script>alert('xss')</script>", "XSS attempt"),
        ("javascript:alert('xss')", "JS protocol"),
        ("<img src=x onerror=alert(1)>", "HTML img onerror"),

        # Path traversal attempts
        ("../../../etc/passwd", "Path traversal"),
        ("..\\..\\..\\windows\\system32", "Windows path traversal"),

        # Code with weird formatting
        ("```\n```python\n```", "Empty code blocks"),
        ("`unclosed backtick", "Unclosed backtick"),
        ("```python\n" + "print(1)" * 1000 + "\n```", "1000 print statements"),

        # Mixed content chaos
        ("👾 ERP: SKU-🆔-12345 in 📁 /tmp/../etc/passwd <script>alert()</script>", "Everything mixed"),
        ("SKU-99999; DROP TABLE users; def hack(): pass", "Code + SQL + ERP mix"),

        # Boundary conditions
        ("a" * 1, "Single character"),
        ("A" * 500, "500 character query"),
        ("A" * 5000, "5k character query"),

        # Special characters that might break parsers
        ("query|with|pipes", "Pipe characters"),
        ("query&&with&&amps", "Ampersands"),
        ("query**with**stars", "Double asterisks"),
        ("query??with??questions", "Double questions"),
        ("query!!with!!exclamations", "Double exclamations"),

        # Multiple backticks
        ("`` double backticks", "Double backticks"),
        ("```triple backticks```", "Triple backticks"),
        ("````quad backticks````", "Quad backticks"),
    ]

    print("=== ADVERSARIAL ROUTING TEST ===\n")

    failed_cases = []
    crashed_cases = []

    for query, description in test_cases:
        try:
            result = classify_query(query)
            route = result.get("route_name", "UNKNOWN")
            confidence = result.get("confidence", 0)
            reasons = result.get("reasons", [])

            # Check for suspicious results
            issues = []

            # Should always have a route
            if not route or route not in ["code", "erp", "docs"]:
                issues.append(f"Suspicious route: {route}")

            # Confidence should be between 0 and 1
            if not (0 <= confidence <= 1):
                issues.append(f"Invalid confidence: {confidence}")

            # Should have at least one reason (except for empty/whitespace)
            if query.strip() and not reasons:
                issues.append("No reasons provided for non-empty query")

            # Reasons should be strings
            if not all(isinstance(r, str) for r in reasons):
                issues.append("Reasons contain non-string values")

            if issues:
                failed_cases.append({
                    "description": description,
                    "query": query[:100] + ("..." if len(query) > 100 else ""),
                    "result": result,
                    "issues": issues
                })
                print(f"❌ {description}")
                print(f"   Query: {query[:80]}")
                print(f"   Route: {route}, Confidence: {confidence}")
                print(f"   Issues: {issues}")
                print()
            else:
                print(f"✅ {description} → {route} ({confidence})")

        except Exception as e:
            crashed_cases.append({
                "description": description,
                "query": query[:100],
                "error": str(e)
            })
            print(f"💥 CRASH: {description}")
            print(f"   Query: {query[:80]}")
            print(f"   Error: {e}")
            print()

    # Summary
    print("\n" + "="*60)
    print(f"SUMMARY: {len(test_cases)} test cases")
    print(f"✅ Passed: {len(test_cases) - len(failed_cases) - len(crashed_cases)}")
    print(f"⚠️  Issues: {len(failed_cases)}")
    print(f"💥 Crashes: {len(crashed_cases)}")
    print("="*60)

    if failed_cases:
        print("\n--- FAILED CASES WITH ISSUES ---")
        for case in failed_cases:
            print(f"\n{case['description']}")
            print(f"  Issues: {', '.join(case['issues'])}")

    if crashed_cases:
        print("\n--- CRASHED CASES ---")
        for case in crashed_cases:
            print(f"\n{case['description']}")
            print(f"  Error: {case['error']}")

    return len(failed_cases) + len(crashed_cases)

if __name__ == "__main__":
    failures = test_adversarial_inputs()
    sys.exit(min(failures, 100))  # Cap exit code
