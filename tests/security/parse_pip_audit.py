import json

with open('./tests/REPORTS/current/pip_audit_report.json') as f:
    data = json.load(f)

for dep in data['dependencies']:
    if 'vulns' in dep and dep['vulns']:
        print(f"Package: {dep['name']}@{dep['version']}")
        for vuln in dep['vulns']:
            print(f"  ID: {vuln['id']}")
            print(f"  Fix Versions: {vuln['fix_versions']}")
            print(f"  Description: {vuln['description']}")
        print("-" * 20)