# app/extensions.py

import os
import logging
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from dotenv import load_dotenv
from supabase import create_client, Client

# Load variables from .env in BACKEND/
load_dotenv()

db = SQLAlchemy()
migrate = Migrate()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    or os.getenv("SUPABASE_ANON_KEY")
)

supabase: Client | None = None

if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    # Optional: a safe log message without the full key
    print("Supabase client initialized")
else:
    print("WARNING: Supabase URL or KEY not set. Supabase client is disabled.")


# Note: Socket.IO removed — realtime features disabled by default.
socketio = None


def get_supabase_status():
    """Return a small dict describing whether Supabase is configured.

    This intentionally does not expose keys. Useful for health checks and
    clearer error messages when running locally.
    """
    missing = []
    if not SUPABASE_URL:
        missing.append("SUPABASE_URL")
    if not SUPABASE_KEY:
        # Could be SERVICE_ROLE_KEY or ANON_KEY — report a generic key missing
        missing.append("SUPABASE_KEY")

    return {
        "ready": bool(SUPABASE_URL and SUPABASE_KEY),
        "missing": missing,
    }


# Print which env vars are present at startup (non-secret, presence only)
_present = []
if SUPABASE_URL:
    _present.append('SUPABASE_URL')
if os.getenv('SUPABASE_SERVICE_ROLE_KEY'):
    _present.append('SUPABASE_SERVICE_ROLE_KEY')
elif os.getenv('SUPABASE_ANON_KEY'):
    _present.append('SUPABASE_ANON_KEY')

if _present:
    print("Supabase env vars present:", ", ".join(_present))
else:
    print("Supabase env vars not present; check .env or environment variables")


redis_conn = None
queue = None

# Try real Redis first, fall back to fakeredis, otherwise use an inline
# dummy queue.
try:
    from redis import Redis
    redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    redis_conn = Redis.from_url(redis_url, socket_connect_timeout=2)
    redis_conn.ping()
    logging.getLogger(__name__).info("Connected to Redis at %s", redis_url)
except Exception as exc:  # pragma: no cover
    logging.getLogger(__name__).warning(
        "Redis unavailable: %s — trying fakeredis", exc
    )
    try:
        import fakeredis
        redis_conn = fakeredis.FakeRedis()
        logging.getLogger(__name__).info("Using fakeredis in-memory backend")
    except Exception:
        redis_conn = None
        logging.getLogger(__name__).warning(
            "fakeredis not installed; using inline queue fallback"
        )

# Provide a queue: RQ.Queue when Redis present, otherwise a
# simple inline executor
try:
    if redis_conn is not None:
        from rq import Queue
        queue = Queue("default", connection=redis_conn)
    else:
        class _InlineQueue:
            def enqueue(self, func, *args, **kwargs):
                job_name = getattr(func, "__name__", str(func))
                logging.getLogger(__name__).info(
                    "Inline executing job: %s", job_name
                )
                try:
                    return func(*args, **kwargs)
                except Exception:
                    logging.getLogger(__name__).exception("Inline job failed")
                    return None
        queue = _InlineQueue()
except Exception:
    queue = None
