"""
Systemd integration for LLMC RAG Service.

Handles service lifecycle management via systemd, with graceful fallback
to fork() mode on systems without systemd.
"""

import os
from pathlib import Path
import subprocess

SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"
SERVICE_NAME = "llmc-rag.service"


class SystemdManager:
    """Manages systemd service lifecycle."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.service_file = SYSTEMD_USER_DIR / SERVICE_NAME

    def is_systemd_available(self) -> bool:
        """Check if systemd user session is actually accessible."""
        try:
            # Check if we can list services (requires working D-Bus connection)
            result = subprocess.run(
                ["systemctl", "--user", "list-units", "--type=service", "--no-pager"],
                check=False,
                capture_output=True,
                timeout=5,
                text=True,
            )
            # If we get "Failed to connect to bus" or similar, systemd isn't usable
            if "Failed to connect to bus" in result.stderr:
                return False
            return result.returncode == 0
        except Exception:
            return False

    def install_service(self) -> bool:
        """Generate and install systemd service file."""
        SYSTEMD_USER_DIR.mkdir(parents=True, exist_ok=True)

        llmc_rag_path = self.repo_root / "scripts" / "llmc-rag"

        service_content = f"""[Unit]
Description=LLMC RAG Enrichment Service
After=network.target

[Service]
Type=simple
ExecStart={llmc_rag_path} _daemon_loop
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

# Environment
Environment="PATH={os.environ.get("PATH", "")}"
Environment="PYTHONPATH={self.repo_root}"

[Install]
WantedBy=default.target
"""

        self.service_file.write_text(service_content)

        # Reload systemd
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)

        return True

    def start(self) -> tuple[bool, str]:
        """Start the service via systemd."""
        if not self.service_file.exists():
            if not self.install_service():
                return False, "Failed to install service file"

        try:
            subprocess.run(
                ["systemctl", "--user", "start", SERVICE_NAME],
                check=True,
                capture_output=True,
                text=True,
            )
            return True, "Service started"
        except subprocess.CalledProcessError as e:
            return False, e.stderr

    def stop(self) -> tuple[bool, str]:
        """Stop the service via systemd."""
        try:
            subprocess.run(
                ["systemctl", "--user", "stop", SERVICE_NAME],
                check=True,
                capture_output=True,
                text=True,
            )
            return True, "Service stopped"
        except subprocess.CalledProcessError as e:
            return False, e.stderr

    def restart(self) -> tuple[bool, str]:
        """Restart the service via systemd."""
        try:
            subprocess.run(
                ["systemctl", "--user", "restart", SERVICE_NAME],
                check=True,
                capture_output=True,
                text=True,
            )
            return True, "Service restarted"
        except subprocess.CalledProcessError as e:
            return False, e.stderr

    def status(self) -> dict:
        """Get service status from systemd."""
        try:
            result = subprocess.run(
                ["systemctl", "--user", "status", SERVICE_NAME],
                check=False,
                capture_output=True,
                text=True,
            )

            # Parse systemctl status output
            is_active = "Active: active" in result.stdout
            is_running = is_active and "running" in result.stdout

            # Extract PID if running
            pid = None
            for line in result.stdout.split("\n"):
                if "Main PID:" in line:
                    parts = line.split()
                    if len(parts) >= 3:
                        try:
                            pid = int(parts[2])
                        except ValueError:
                            pass

            return {
                "running": is_running,
                "active": is_active,
                "pid": pid,
                "status_text": result.stdout,
            }
        except Exception as e:
            return {"running": False, "active": False, "pid": None, "error": str(e)}

    def enable(self) -> tuple[bool, str]:
        """Enable service to start on boot."""
        try:
            subprocess.run(
                ["systemctl", "--user", "enable", SERVICE_NAME],
                check=True,
                capture_output=True,
                text=True,
            )
            return True, "Service enabled for boot"
        except subprocess.CalledProcessError as e:
            return False, e.stderr

    def disable(self) -> tuple[bool, str]:
        """Disable service from starting on boot."""
        try:
            subprocess.run(
                ["systemctl", "--user", "disable", SERVICE_NAME],
                check=True,
                capture_output=True,
                text=True,
            )
            return True, "Service disabled"
        except subprocess.CalledProcessError as e:
            return False, e.stderr

    def get_logs(self, lines: int = 50, follow: bool = False) -> subprocess.Popen | None:
        """Get logs via journalctl."""
        cmd = ["journalctl", "--user", "-u", SERVICE_NAME, "-n", str(lines)]

        if follow:
            cmd.append("-f")
            # Return process handle for streaming
            return subprocess.Popen(cmd)
        else:
            # Return output directly
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            print(result.stdout)
            return None
