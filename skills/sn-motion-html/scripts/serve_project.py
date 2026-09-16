#!/usr/bin/env python3
"""Serve a generated project for local preview.

Only the files the page actually requests are reachable: the HTML entry point,
its stylesheet, src/ JavaScript, content/ JSON, final media under assets/, and
the two exported deliverables (the storyboard HTML and the story poster).
Configuration, prompts, scripts, the Markdown storyboard, private state,
temporary files, dotfiles, and directory listings are all refused. This is a
local preview server, not a production deployment target.
"""

from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import mimetypes
from pathlib import Path, PurePosixPath
import sys
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_model import SERVED_EXPORTS, web_visible  # noqa: E402

CHUNK = 64 * 1024

# Explicit types: mimetypes leans on the Windows registry and returns
# application/octet-stream for .webp and text/plain for .js on some machines.
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".webp": "image/webp",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".avif": "image/avif",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".ico": "image/x-icon",
}


def content_type_for(name: str) -> str:
    suffix = Path(name).suffix.lower()
    return CONTENT_TYPES.get(suffix) or mimetypes.guess_type(name)[0] or "application/octet-stream"


class PreviewHandler(SimpleHTTPRequestHandler):
    server_version = "SNMotionHTMLPreview/1.0"

    def _relative_target(self) -> str | None:
        raw = unquote(urlsplit(self.path).path)
        parts = [part for part in PurePosixPath(raw).parts if part not in {"", "/", "."}]
        if any(part == ".." for part in parts):
            return None
        if not parts:
            return "index.html"
        return "/".join(parts)

    def _resolve(self, relative: str) -> Path | None:
        root = Path(self.directory).resolve()
        try:
            candidate = (root / relative).resolve()
            candidate.relative_to(root)
        except (ValueError, OSError):
            return None
        return candidate

    def _allowed(self) -> Path | None:
        relative = self._relative_target()
        if relative is None:
            return None
        # Video suffixes stay allowed so one preview command serves both modes.
        if not web_visible(relative, "video"):
            return None
        target = self._resolve(relative)
        if target is None or not target.is_file():
            return None
        return target

    def list_directory(self, path):  # noqa: D102 - directory listings stay off
        self.send_error(404, "No directory listing")
        return None

    def _send_file(self, target: Path, include_body: bool) -> None:
        size = target.stat().st_size
        content_type = content_type_for(target.name)
        start, end, status = 0, size - 1, 200

        header = self.headers.get("Range") or ""
        if size and header.startswith("bytes="):
            spec = header[len("bytes="):].split(",")[0].strip()
            first, _, last = spec.partition("-")
            try:
                if first:
                    start = int(first)
                    end = int(last) if last else size - 1
                else:
                    start = max(0, size - int(last))
                    end = size - 1
            except ValueError:
                start, end = 0, size - 1
            if start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            end = min(end, size - 1)
            status = 206

        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not include_body:
            return

        remaining = end - start + 1
        with target.open("rb") as handle:
            handle.seek(start)
            while remaining > 0:
                chunk = handle.read(min(CHUNK, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        target = self._allowed()
        if target is None:
            self.send_error(404, "Not served by this preview")
            return
        self._send_file(target, include_body=True)

    def do_HEAD(self) -> None:  # noqa: N802 - stdlib naming
        target = self._allowed()
        if target is None:
            self.send_error(404, "Not served by this preview")
            return
        self._send_file(target, include_body=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()

    root = args.project_root.expanduser().resolve()
    if not (root / "index.html").is_file():
        raise SystemExit(f"no index.html found in {root}; initialize a project first")

    handler = partial(PreviewHandler, directory=str(root))
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Serving {root} at http://{args.host}:{args.port}/")
    print("Local preview only. Serves index.html, styles.css, src/, content/, assets/, and the exported deliverables.")
    for relative in SERVED_EXPORTS:
        if (root / relative).is_file():
            print(f"Export: http://{args.host}:{args.port}/{relative}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
