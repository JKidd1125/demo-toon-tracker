"""Small, private WoW character tracker using only the Python standard library."""

from __future__ import annotations

import base64
import json
import logging
import os
import sqlite3
import threading
import time
from contextlib import closing
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import error, parse, request


ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"


def load_local_env() -> None:
    """Make a private local .env.local convenient without adding a dependency."""
    env_file = ROOT / ".env.local"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


load_local_env()
DATA_DIR = Path(os.environ.get("DATA_DIR", str(ROOT / "data")))
DATABASE = DATA_DIR / "snapshots.sqlite3"
REGION = "eu"
REALM = "silvermoon"
CHARACTER = "uther"
DEMO_MODE = os.environ.get("DEMO_MODE", "true").lower() in {"1", "true", "yes"}
INTERVAL_HOURS = max(1, int(os.environ.get("FETCH_INTERVAL_HOURS", "24")))
PORT = int(os.environ.get("PORT", "8080"))
HOST = os.environ.get("HOST", "127.0.0.1")
LOG = logging.getLogger("demo-toon-tracker")
REFRESH_LOCK = threading.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with closing(connect()) as db, db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute(
            """CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY,
                fetched_at TEXT NOT NULL,
                name TEXT NOT NULL,
                realm TEXT NOT NULL,
                level INTEGER,
                class_name TEXT,
                specialization TEXT,
                item_level INTEGER,
                achievement_points INTEGER,
                is_demo INTEGER NOT NULL DEFAULT 0
            )"""
        )
        db.execute(
            """CREATE TABLE IF NOT EXISTS refresh_attempts (
                id INTEGER PRIMARY KEY,
                attempted_at TEXT NOT NULL,
                succeeded INTEGER NOT NULL,
                message TEXT NOT NULL
            )"""
        )


def nested_name(value: object) -> str | None:
    if isinstance(value, dict):
        value = value.get("name")
    return value if isinstance(value, str) else None


def normalize_profile(profile: dict, is_demo: bool = False) -> dict:
    """Keep only fields the dashboard uses; absent API fields stay absent."""
    if not isinstance(profile, dict) or not isinstance(profile.get("name"), str):
        raise ValueError("The character response did not contain a name")
    return {
        "fetched_at": now_iso(),
        "name": profile["name"],
        "realm": nested_name(profile.get("realm")) or "Silvermoon",
        "level": profile.get("level") if isinstance(profile.get("level"), int) else None,
        "class_name": nested_name(profile.get("character_class")),
        "specialization": nested_name(profile.get("active_spec")),
        "item_level": profile.get("equipped_item_level") if isinstance(profile.get("equipped_item_level"), int) else None,
        "achievement_points": profile.get("achievement_points") if isinstance(profile.get("achievement_points"), int) else None,
        "is_demo": int(is_demo),
    }


def demo_profile() -> dict:
    # Explicitly illustrative: these values are never presented as Uther's real stats.
    return {
        "name": "Uther",
        "realm": {"name": "Silvermoon"},
        "level": 90,
        "character_class": {"name": "Sample class"},
        "active_spec": {"name": "Sample spec"},
        "equipped_item_level": 250,
        "achievement_points": 1000,
    }


def fetch_profile() -> dict:
    client_id = os.environ.get("BLIZZARD_CLIENT_ID", "")
    client_secret = os.environ.get("BLIZZARD_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        raise RuntimeError("Blizzard credentials are missing")

    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    token_request = request.Request(
        "https://eu.battle.net/oauth/token",
        data=b"grant_type=client_credentials",
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "DemoToonTracker/0.1 (private learning project)",
        },
        method="POST",
    )
    with request.urlopen(token_request, timeout=15) as response:
        token = json.load(response).get("access_token")
    if not token:
        raise RuntimeError("Blizzard did not return an access token")

    path = f"/profile/wow/character/{REALM}/{CHARACTER}"
    query = parse.urlencode({"namespace": "profile-eu", "locale": "en_GB"})
    profile_request = request.Request(
        f"https://eu.api.blizzard.com{path}?{query}",
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "DemoToonTracker/0.1 (private learning project)",
        },
    )
    with request.urlopen(profile_request, timeout=15) as response:
        return json.load(response)


def refresh() -> tuple[bool, str]:
    if not REFRESH_LOCK.acquire(blocking=False):
        return False, "A refresh is already running"
    try:
        try:
            raw = demo_profile() if DEMO_MODE else fetch_profile()
            snapshot = normalize_profile(raw, is_demo=DEMO_MODE)
            with closing(connect()) as db, db:
                db.execute(
                    """INSERT INTO snapshots
                    (fetched_at, name, realm, level, class_name, specialization,
                     item_level, achievement_points, is_demo)
                    VALUES (:fetched_at, :name, :realm, :level, :class_name,
                            :specialization, :item_level, :achievement_points, :is_demo)""",
                    snapshot,
                )
                db.execute(
                    "INSERT INTO refresh_attempts (attempted_at, succeeded, message) VALUES (?, 1, ?)",
                    (snapshot["fetched_at"], "Demo snapshot saved" if DEMO_MODE else "Profile updated"),
                )
            return True, "Demo snapshot saved" if DEMO_MODE else "Profile updated"
        except error.HTTPError as exc:
            message = f"Blizzard returned HTTP {exc.code}"
        except (error.URLError, TimeoutError):
            message = "Could not reach Blizzard"
        except (ValueError, RuntimeError) as exc:
            message = str(exc)
        except Exception:
            LOG.exception("Unexpected refresh failure")
            message = "Unexpected refresh failure; check the server log"
        try:
            with closing(connect()) as db, db:
                db.execute(
                    "INSERT INTO refresh_attempts (attempted_at, succeeded, message) VALUES (?, 0, ?)",
                    (now_iso(), message),
                )
        except sqlite3.Error:
            LOG.exception("Could not record the failed refresh")
        LOG.warning("Refresh failed: %s", message)
        return False, message
    finally:
        REFRESH_LOCK.release()


def current_state() -> dict:
    with closing(connect()) as db:
        latest = db.execute("SELECT * FROM snapshots ORDER BY id DESC LIMIT 1").fetchone()
        attempts = db.execute("SELECT * FROM refresh_attempts ORDER BY id DESC LIMIT 1").fetchone()
        history = db.execute(
            "SELECT fetched_at, level, item_level, is_demo FROM snapshots WHERE is_demo = ? ORDER BY id DESC LIMIT 30",
            (int(DEMO_MODE),),
        ).fetchall()
    # A real run should never display old demo values as live character data.
    if latest and bool(latest["is_demo"]) != DEMO_MODE:
        latest = None
        history = []
    return {
        "mode": "demo" if DEMO_MODE else "live",
        "target": {"name": "Uther", "realm": "Silvermoon", "region": "EU Retail"},
        "latest": dict(latest) if latest else None,
        "last_attempt": dict(attempts) if attempts else None,
        "history": [dict(row) for row in reversed(history)],
    }


class Handler(BaseHTTPRequestHandler):
    def send_bytes(self, content: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def send_json(self, value: dict, status: int = 200) -> None:
        self.send_bytes(json.dumps(value).encode(), "application/json; charset=utf-8", status)

    def do_GET(self) -> None:
        route = parse.urlsplit(self.path).path
        if route == "/healthz":
            self.send_json({"status": "ok"})
            return
        if route == "/readyz":
            try:
                with closing(connect()) as db:
                    db.execute("SELECT 1").fetchone()
                self.send_json({"status": "ready"})
            except sqlite3.Error:
                self.send_json({"status": "database unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        if route == "/api/state":
            try:
                self.send_json(current_state())
            except sqlite3.Error:
                LOG.exception("Could not read character data")
                self.send_json({"error": "Character data is unavailable"}, HTTPStatus.SERVICE_UNAVAILABLE)
            return
        static_files = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/app.js": ("app.js", "application/javascript; charset=utf-8"),
            "/style.css": ("style.css", "text/css; charset=utf-8"),
        }
        if route in static_files:
            filename, mime = static_files[route]
            self.send_bytes((STATIC / filename).read_bytes(), mime)
            return
        self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if parse.urlsplit(self.path).path != "/api/refresh":
            self.send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        if self.headers.get("Content-Length", "0") not in {"0", ""}:
            self.send_json({"error": "Request body is not accepted"}, HTTPStatus.BAD_REQUEST)
            return
        success, message = refresh()
        self.send_json(
            {"ok": success, "message": message},
            HTTPStatus.OK if success else HTTPStatus.BAD_GATEWAY,
        )

    def log_message(self, fmt: str, *args: object) -> None:
        LOG.info("%s %s", self.client_address[0], fmt % args)


def scheduler() -> None:
    while True:
        try:
            state = current_state()
        except sqlite3.Error:
            LOG.exception("Could not read refresh state")
            time.sleep(60)
            continue
        last_attempt = state["last_attempt"]
        should_refresh = not last_attempt or (state["latest"] is None and bool(last_attempt["succeeded"]))
        if last_attempt:
            elapsed = datetime.now(timezone.utc) - datetime.fromisoformat(last_attempt["attempted_at"])
            retry_seconds = INTERVAL_HOURS * 3600 if last_attempt["succeeded"] else 15 * 60
            should_refresh = should_refresh or elapsed.total_seconds() >= retry_seconds
        if should_refresh:
            refresh()
        time.sleep(60)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    initialize_database()
    threading.Thread(target=scheduler, daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    LOG.info("Tracking %s on %s EU; mode=%s; listening on %s:%s", CHARACTER, REALM, "demo" if DEMO_MODE else "live", HOST, PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
