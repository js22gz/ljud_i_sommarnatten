#!/usr/bin/env python3
"""Analyze, build, and preview a recording session."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from sessions import list_sessions, load_session

ROOT = Path(__file__).resolve().parent
PYTHON = ROOT / ".venv" / "bin" / "python"


def run_script(script: str, *args: str) -> None:
    cmd = [str(PYTHON if PYTHON.exists() else sys.executable), str(ROOT / script), *args]
    subprocess.run(cmd, check=True, cwd=ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the full pipeline for a recording session.",
        epilog="Example: python run.py midsommardagen_08_20 --serve",
    )
    parser.add_argument("session", nargs="?", help="Session id (folder name under sessions/)")
    parser.add_argument("--list", action="store_true", help="List available sessions")
    parser.add_argument("--analyze", action="store_true", help="Run BirdNET analysis only")
    parser.add_argument("--build", action="store_true", help="Build visualizer only")
    parser.add_argument("--serve", action="store_true", help="Start local preview server")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Build and copy session to docs/ for GitHub Pages",
    )
    parser.add_argument("--skip-birdnet", action="store_true", help="Reuse existing BirdNET CSV")
    parser.add_argument("--port", type=int, default=8765, help="Preview server port")
    args = parser.parse_args()

    if args.list:
        for session_id in list_sessions():
            print(session_id)
        return

    if not args.session:
        parser.error("session id required (or use --list)")

    session = load_session(args.session)
    only_one_step = args.analyze or args.build or args.serve or args.publish
    run_all = not only_one_step

    if run_all or args.analyze:
        analyze_args = ["--session", session.id]
        if args.skip_birdnet:
            analyze_args.append("--skip-birdnet")
        run_script("analyze.py", *analyze_args)

    if run_all or args.build or args.publish:
        build_args = ["--session", session.id]
        if args.publish:
            build_args.append("--publish")
        run_script("build_visualizer.py", *build_args)

    if args.serve:
        print(f"\nPreview: http://127.0.0.1:{args.port}/")
        run_script("serve.py", "--session", session.id, "--port", str(args.port))


if __name__ == "__main__":
    main()