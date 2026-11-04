import hashlib
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from prometheus_client import Counter, Histogram, start_http_server

POD_NAME = os.environ.get("HOSTNAME", "local")

REQUESTS = Counter(
    "raid_requests_total",
    "Completed simulated raid requests",
    ["status"],
)
DURATION = Histogram(
    "raid_request_duration_seconds",
    "Time spent processing a simulated raid request",
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

# Make both status series visible before the first request.
REQUESTS.labels(status="200")
REQUESTS.labels(status="500")


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            self.reply(200, {"status": "ok"})
            return

        if self.path == "/":
            self.reply(200, {
                "application": "Raid Simulator",
                "pod": POD_NAME,
                "purpose": "Synthetic traffic for a local scaling demonstration",
            })
            return

        if self.path != "/work":
            self.reply(404, {"error": "Not found"})
            return

        started = time.perf_counter()
        status = 200
        try:
            # Fixed, bounded CPU work; no external API or database calls.
            hashlib.pbkdf2_hmac(
                "sha256", b"raid-simulation", b"local-demo", 120_000
            )
            result = {"pod": POD_NAME, "message": "Simulated raid processed"}
        except Exception:
            status = 500
            result = {"pod": POD_NAME, "error": "Processing failed"}

        DURATION.observe(time.perf_counter() - started)
        REQUESTS.labels(status=str(status)).inc()
        self.reply(status, result)

    def reply(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    start_http_server(8000)
    print(f"Raid Simulator starting on pod {POD_NAME}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
