"""HTTP receiver for the Samsung Health companion app.

Streamlit can't accept a POST, so this is a separate stdlib process the phone
pushes to over the LAN. Every request needs
``Authorization: Bearer $FITME_SYNC_TOKEN``; the server refuses to start
without a token configured. Plain HTTP — keep it on the LAN (or behind
Tailscale), never exposed to the internet.

Endpoints::

    POST /samsung/sync     payload JSON (see fitme.samsung) -> {"ingested": {...}}
    GET  /samsung/status   -> {"sync_state": [{data_type, synced_at, rows}]}

CLI::

    uv run python -m fitme.receiver                      # 127.0.0.1:8765
    uv run python -m fitme.receiver --host 0.0.0.0       # reachable from the phone
"""
from __future__ import annotations

import argparse
import hmac
import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from fitme import queries, samsung
from fitme.config import load as load_settings
from fitme.db import connect
from fitme.logging_config import setup as setup_logging

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
MAX_BODY_BYTES = 10 * 1024 * 1024


class _Handler(BaseHTTPRequestHandler):
    server_version = "fitme-receiver/0.1"
    token: str = ""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 — stdlib signature
        logger.info("%s %s", self.address_string(), format % args)

    def _send_json(self, status: HTTPStatus, body: dict) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _error(self, status: HTTPStatus, message: str) -> None:
        # The request body may be unread — don't let it bleed into the next request.
        self.close_connection = True
        self._send_json(status, {"error": message})

    def _authorized(self) -> bool:
        scheme, _, supplied = self.headers.get("Authorization", "").partition(" ")
        ok = scheme.lower() == "bearer" and hmac.compare_digest(
            supplied.strip().encode("utf-8"), self.token.encode("utf-8")
        )
        if not ok:
            self._error(HTTPStatus.UNAUTHORIZED, "invalid or missing bearer token")
        return ok

    def do_GET(self) -> None:  # noqa: N802 — stdlib naming
        if self.path != "/samsung/status":
            self._error(HTTPStatus.NOT_FOUND, "not found")
            return
        if not self._authorized():
            return
        with connect() as conn:
            state = queries.sh_sync_state(conn)
        self._send_json(HTTPStatus.OK, {"sync_state": state})

    def do_POST(self) -> None:  # noqa: N802 — stdlib naming
        if self.path != "/samsung/sync":
            self._error(HTTPStatus.NOT_FOUND, "not found")
            return
        if not self._authorized():
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._error(HTTPStatus.LENGTH_REQUIRED, "Content-Length required")
            return
        if length < 0:
            self._error(HTTPStatus.BAD_REQUEST, "invalid Content-Length")
            return
        if length > MAX_BODY_BYTES:
            self._error(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                f"body larger than {MAX_BODY_BYTES} bytes",
            )
            return
        try:
            payload = json.loads(self.rfile.read(length))
        except (ValueError, RecursionError):
            self._error(HTTPStatus.BAD_REQUEST, "body is not valid JSON")
            return
        try:
            with connect() as conn:
                counts = samsung.ingest_payload(conn, payload)
        except samsung.PayloadError as err:
            self._error(HTTPStatus.BAD_REQUEST, str(err))
            return
        except Exception:
            logger.exception("samsung ingest failed")
            self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "ingest failed")
            return
        logger.info("samsung sync ingested %s", counts)
        self._send_json(HTTPStatus.OK, {"ingested": counts})


def make_server(host: str, port: int, token: str) -> ThreadingHTTPServer:
    """Build the receiver bound to ``host:port`` (``port=0`` picks a free one)."""
    if not token:
        raise ValueError("a sync token is required")
    handler = type("Handler", (_Handler,), {"token": token})
    return ThreadingHTTPServer((host, port), handler)


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    parser = argparse.ArgumentParser(
        prog="fitme.receiver",
        description="Receive Samsung Health payloads from the companion Android app.",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"bind address (default: {DEFAULT_HOST}; use 0.0.0.0 for the LAN)",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    token = load_settings().sync_token
    if not token:
        logger.error("FITME_SYNC_TOKEN is not set — refusing to start without a token.")
        return 2

    server = make_server(args.host, args.port, token)
    logger.info("receiver listening on http://%s:%d", args.host, server.server_port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("receiver stopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
