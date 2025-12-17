import shlex

cmd = "ls -la; echo Pwned"
parts = shlex.split(cmd)
print(f"Parts: {parts}")
binary = parts[0]
print(f"Binary: {binary}")

# Simulate validate_command
blacklist = []
if binary in blacklist:
    print("Blocked")
else:
    print("Allowed")
    # Simulate run_cmd
    # subprocess.run(cmd, shell=True)
