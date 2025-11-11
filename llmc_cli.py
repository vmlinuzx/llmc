#!/usr/bin/env python3
"""
LLMC Unified CLI - Single entry point for all LLM operations
Provides structured logging, correlation IDs, and flag mapping to gateway
"""

import argparse
import json
import os
import sys
import subprocess
import uuid
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

class LLMC_CLI:
    """Unified LLM Commander CLI with structured logging and correlation IDs."""

    def __init__(self):
        self.correlation_id = self._generate_correlation_id()
        self.exec_root = Path(__file__).parent
        self.gateway_script = self.exec_root / "scripts" / "llm_gateway.sh"

    def _generate_correlation_id(self) -> str:
        """Generate correlation ID for telemetry."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        random_suffix = str(uuid.uuid4())[:8]
        return f"{timestamp}-{random_suffix}"

    def _log_event(self, event: str, data: Dict[str, Any]):
        """Log structured JSON event with correlation ID."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "correlationId": self.correlation_id,
            "event": event,
            "service": "llmc_cli",
            **data
        }
        print(json.dumps(log_entry, separators=(',', ':')), file=sys.stderr)

    def _check_gateway_exists(self) -> bool:
        """Check if gateway script exists."""
        return self.gateway_script.exists() and os.access(self.gateway_script, os.X_OK)

    def _call_gateway(self, prompt: str, args: argparse.Namespace) -> str:
        """Call the gateway with proper environment variables and arguments."""
        if not self._check_gateway_exists():
            raise FileNotFoundError(f"Gateway script not found: {self.gateway_script}")

        # Build environment variables
        env = os.environ.copy()

        # RAG configuration
        if hasattr(args, 'rag') and args.rag:
            env['RAG_ENABLED'] = '1'
            self._log_event("cli.rag.enabled", {"enabled": True})
        else:
            env['RAG_ENABLED'] = '0'
            self._log_event("cli.rag.disabled", {"disabled": True})

        # Set correlation ID for gateway
        env['LLMC_CORRELATION_ID'] = self.correlation_id

        # Set provider-specific flags
        gateway_args = []

        if hasattr(args, 'provider'):
            if args.provider == 'local':
                gateway_args.append('--local')
            elif args.provider == 'api':
                gateway_args.append('--api')
            elif args.provider == 'claude':
                gateway_args.append('--claude')
            elif args.provider == 'gemini':
                gateway_args.append('--gemini')
            elif args.provider == 'azure':
                gateway_args.append('--azure-codex')

        # Additional flags
        if hasattr(args, 'yolo') and args.yolo:
            gateway_args.append('--yolo')

        if hasattr(args, 'minimax') and args.minimax:
            gateway_args.append('--minimax')

        # Add debug flag if verbose
        if hasattr(args, 'verbose') and args.verbose:
            gateway_args.append('--debug')

        # Build command
        cmd = [str(self.gateway_script)] + gateway_args + [prompt]

        self._log_event("cli.gateway.call", {
            "command": " ".join(cmd),
            "correlationId": self.correlation_id
        })

        try:
            start_time = time.time()
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            duration = time.time() - start_time

            if result.returncode == 0:
                self._log_event("cli.gateway.success", {
                    "duration": duration,
                    "stdout_lines": len(result.stdout.splitlines())
                })
                return result.stdout.strip()
            else:
                error_msg = f"Gateway failed with exit code {result.returncode}"
                if result.stderr:
                    error_msg += f": {result.stderr.strip()}"

                self._log_event("cli.gateway.error", {
                    "duration": duration,
                    "exit_code": result.returncode,
                    "error": error_msg
                })
                raise subprocess.CalledProcessError(result.returncode, cmd, error_msg)

        except subprocess.TimeoutExpired:
            self._log_event("cli.gateway.timeout", {"timeout": 300})
            raise TimeoutError("Gateway call timed out after 5 minutes")
        except Exception as e:
            self._log_event("cli.gateway.exception", {"error": str(e)})
            raise

def create_parser() -> argparse.ArgumentParser:
    """Create argument parser for the CLI."""
    parser = argparse.ArgumentParser(
        description="LLMC - Unified LLM Commander CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  llmc_cli "What files exist in the scripts directory?" --provider local
  llmc_cli "Explain this code" --provider api --rag
  llmc_cli --claude "Write a function" --verbose
        """)

    # Main prompt argument
    parser.add_argument("prompt", nargs="?", help="The prompt to send to the LLM")
    parser.add_argument("--stdin", action="store_true",
                       help="Read prompt from stdin")

    # Provider selection
    parser.add_argument("--provider", choices=['local', 'api', 'claude', 'gemini', 'azure', 'minimax'],
                       default='api', help="LLM provider to use (default: api)")

    # Feature flags
    parser.add_argument("--rag", action="store_true", help="Enable RAG enrichment")
    parser.add_argument("--yolo", action="store_true", help="Enable YOLO mode")
    parser.add_argument("--minimax", action="store_true", help="Use MiniMax provider")

    # Output and debugging
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--correlation-id", help="Use specific correlation ID")

    return parser

def main():
    """Main entry point for the CLI."""
    cli = LLMC_CLI()
    parser = create_parser()
    args = parser.parse_args()

    # Override correlation ID if provided
    if args.correlation_id:
        cli.correlation_id = args.correlation_id

    # Start logging
    cli._log_event("cli.start", {
        "args": vars(args),
        "python_version": sys.version,
        "platform": sys.platform
    })

    try:
        # Get prompt
        if args.stdin:
            if args.prompt:
                parser.error("Cannot specify both prompt and --stdin")
            prompt = sys.stdin.read().strip()
            if not prompt:
                parser.error("No input provided via stdin")
        elif args.prompt:
            prompt = args.prompt
        else:
            # Interactive mode
            print("🎯 LLMC CLI - Interactive Mode")
            print("Enter your prompt (Ctrl+D to end, Ctrl+C to cancel):")
            try:
                prompt = sys.stdin.read().strip()
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                sys.exit(0)

        if not prompt:
            parser.error("No prompt provided")

        cli._log_event("cli.prompt.received", {
            "prompt_length": len(prompt),
            "prompt_preview": prompt[:100] + ("..." if len(prompt) > 100 else "")
        })

        # Call gateway
        response = cli._call_gateway(prompt, args)

        # Output response
        if args.json:
            output = {
                "correlationId": cli.correlation_id,
                "response": response,
                "timestamp": datetime.now().isoformat()
            }
            print(json.dumps(output, indent=2))
        else:
            print(response)

        cli._log_event("cli.complete", {"success": True})
        return 0

    except KeyboardInterrupt:
        cli._log_event("cli.interrupted", {"signal": "SIGINT"})
        print("\n👋 Interrupted by user")
        return 130
    except Exception as e:
        cli._log_event("cli.failure", {"error": str(e), "type": type(e).__name__})

        if args.verbose:
            # In verbose mode, show full traceback
            import traceback
            print(f"❌ Error: {e}", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)
        else:
            print(f"❌ Error: {e}", file=sys.stderr)

        return 1

if __name__ == "__main__":
    sys.exit(main())