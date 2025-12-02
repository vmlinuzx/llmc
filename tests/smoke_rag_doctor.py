
from pathlib import Path
import sys

from textual.app import App

from llmc.tui.screens.rag_doctor import RAGDoctorScreen


class SmokeTestApp(App):
    def on_mount(self):
        self.push_screen(RAGDoctorScreen())
        # We'll just exit after a moment if it didn't crash
        self.set_timer(2.0, self.exit_success)

    def exit_success(self):
        self.exit(0)

if __name__ == "__main__":
    # Mock repo root
    app = SmokeTestApp()
    app.repo_root = Path.cwd()
    
    # We want to run this headless if possible, but Textual needs a driver.
    # We can use the 'dummy' driver for testing logic without UI.
    try:
        app.run(headless=True)
        print("Smoke test passed: RAGDoctorScreen mounted successfully.")
        sys.exit(0)
    except Exception as e:
        print(f"Smoke test failed: {e}")
        sys.exit(1)
