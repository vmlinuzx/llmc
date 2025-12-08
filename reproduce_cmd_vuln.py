
import shlex
from pathlib import Path

def validate_command(cmd_parts, blacklist):
    if not cmd_parts:
        print("Empty command")
        return False
    binary = cmd_parts[0]
    binary_name = Path(binary).name
    print(f"Binary detected: '{binary_name}'")
    
    if binary_name in blacklist:
        print(f"BLOCKED: {binary_name} is blacklisted")
        return False
    return True

blacklist = ["rm", "evil"]

# Test case 1: simple blocked command
cmd1 = "rm -rf /"
parts1 = shlex.split(cmd1)
print(f"Cmd: '{cmd1}' -> Parts: {parts1}")
validate_command(parts1, blacklist)

# Test case 2: chained command (semicolon)
cmd2 = "echo hello; rm -rf /"
parts2 = shlex.split(cmd2)
print(f"\nCmd: '{cmd2}' -> Parts: {parts2}")
validate_command(parts2, blacklist)

# Test case 3: chained command (&&)
cmd3 = "echo hello && rm -rf /"
parts3 = shlex.split(cmd3)
print(f"\nCmd: '{cmd3}' -> Parts: {parts3}")
validate_command(parts3, blacklist)

# Test case 4: quoted semicolon
cmd4 = "echo 'hello; world'"
parts4 = shlex.split(cmd4)
print(f"\nCmd: '{cmd4}' -> Parts: {parts4}")
validate_command(parts4, blacklist)
