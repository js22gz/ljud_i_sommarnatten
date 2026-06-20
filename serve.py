#!/usr/bin/env python3
"""Static file server with HTTP Range support (required for audio seeking)."""

from __future__ import annotations

import argparse
import os
import re
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from socketserver import ThreadingMixIn

from sessions import load_session


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class RangeRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        if getattr(self, "_accept_ranges", False):
            self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def send_head(self):
        path = self.translate_path(self.path)
        self._accept_ranges = os.path.isfile(path)

        if not self._accept_ranges:
            return super().send_head()

        file_size = os.path.getsize(path)
        range_header = self.headers.get("Range")
        if not range_header:
            return super().send_head()

        match = re.match(r"bytes=(\d*)-(\d*)", range_header)
        if not match:
            return super().send_head()

        start = int(match.group(1)) if match.group(1) else 0
        end = int(match.group(2)) if match.group(2) else file_size - 1
        end = min(end, file_size - 1)
        if start > end or start >= file_size:
            self.send_error(416)
            return None

        length = end - start + 1
        content_type = self.guess_type(path)
        with open(path, "rb") as handle:
            handle.seek(start)
            data = handle.read(length)

        self.send_response(206)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.end_headers()
        return data

    def copyfile(self, source, outputfile):
        if isinstance(source, (bytes, bytearray)):
            outputfile.write(source)
            return
        super().copyfile(source, outputfile)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", help="Recording session id (folder under sessions/)")
    parser.add_argument("--directory", type=Path, help="Override directory to serve")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if args.directory:
        serve_dir = args.directory
    elif args.session:
        session = load_session(args.session)
        serve_dir = session.root
    else:
        raise SystemExit("Provide --session <id> or --directory <path>.")

    if not (serve_dir / "index.html").exists():
        raise SystemExit(f"No visualizer in {serve_dir}. Run build_visualizer.py first.")

    os.chdir(serve_dir)
    try:
        server = ThreadingHTTPServer(("", args.port), RangeRequestHandler)
    except OSError as exc:
        if exc.errno == 98:
            raise SystemExit(
                f"Port {args.port} is already in use. Stop the other server or pick --port."
            ) from exc
        raise

    print(f"Serving {serve_dir.resolve()} at http://127.0.0.1:{args.port}/")
    print("Use this server (not python3 -m http.server) for waveform seeking.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()