from flask import Flask, request, jsonify
from config import Config
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room
import os
from dotenv import load_dotenv
import redis
from supabase import create_client
import time

app = Flask(__name__)
app.config.from_object(Config)
app.url_map.strict_slashes = False

CORS(app, origins="*", supports_credentials=True)

# Modern async mode (no eventlet)
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode="threading",  # Safe and works perfectly
    logger=False,
    engineio_logger=False
)

# Redis
try:
    redis_client = redis.Redis.from_url(Config.REDIS_URL)
    redis_client.ping()
    print("Connected to Redis")
except Exception as e:
    print(f"Redis failed: {e}")
    redis_client = None

load_dotenv()  # load .env into os.environ for local dev

# Supabase
SUPABASE_URL = (
    getattr(Config, "SUPABASE_URL", None)
    or os.environ.get("SUPABASE_URL")
)
# accept SERVICE_ROLE_KEY or ANON key env names commonly used in .env
SUPABASE_KEY = (
    getattr(Config, "SUPABASE_KEY", None)
    or os.environ.get("SUPABASE_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_ANON_KEY")
)

if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        # quick health check (no-op if table not present)
        _ = supabase.table("bookings").select("id").limit(1).execute()
        print("Connected to Supabase")
    except Exception as e:
        print(f"Supabase failed: {e}")
        supabase = None
else:
    print("Supabase not configured (SUPABASE_URL/SUPABASE_KEY missing)")
    supabase = None

# Keys
ONLINE_PLUMBERS_KEY = "online:plumbers"
PLUMBER_SOCKET_MAP = "plumber:socket_map"

# State
active_jobs = {}
job_accepted_by = {}
bookings_data = []


@app.after_request
def force_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = (
        "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    )
    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type, Authorization, X-Plumber-ID"
    )
    return response


@app.route("/api/bookings", methods=["GET", "POST", "OPTIONS"])
def bookings():
    if request.method == "OPTIONS":
        return "", 204

    try:
        if request.method == "POST":
            data = request.get_json() or {}
            if not data:
                return jsonify({"success": False, "error": "no data"}), 400

            job = data.copy()
            # local fallback id
            job["job_id"] = str(len(bookings_data) + 1)
            job["status"] = "pending"

            # persist to Supabase if available
            if supabase:
                try:
                    # 1) Upsert/resolve customer into `customers` table
                    customer = None
                    # Accept either nested customer object or top-level fields
                    if isinstance(job.get("customer"), dict):
                        customer = job.get("customer")
                    else:
                        # try common fields
                        customer = {
                            k: job.get(k)
                            for k in (
                                "customer_name", "name", "customer_phone",
                                "phone", "customer_email", "email"
                            )
                            if job.get(k) is not None
                        }
                    customer_id = None
                    if customer:
                        try:
                            # prefer explicit id if provided
                            if customer.get("id"):
                                customer_id = str(customer.get("id"))
                                supabase.table("users").update(
                                    customer
                                ).eq("id", customer_id).execute()
                            else:
                                # try find by phone or email
                                found = None
                                phone = (
                                    customer.get("customer_phone")
                                    or customer.get("phone")
                                )
                                email = (
                                    customer.get("customer_email")
                                    or customer.get("email")
                                )
                                if phone:
                                    fq = (
                                        supabase.table("customers")
                                        .select("*")
                                        .eq("phone", phone)
                                        .limit(1)
                                        .execute()
                                    )
                                    if fq.data:
                                        found = fq.data[0]
                                if not found and email:
                                    fq = (
                                        supabase.table("customers")
                                        .select("*")
                                        .eq("email", email)
                                        .limit(1)
                                        .execute()
                                    )
                                    if fq.data:
                                        found = fq.data[0]

                                if found:
                                    customer_id = str(found.get("id"))
                                    supabase.table("users").update(
                                        customer
                                    ).eq("id", customer_id).execute()
                                else:
                                    ins = (
                                        supabase.table("users")
                                        .insert(customer)
                                        .execute()
                                    )
                                    if (
                                        ins.data
                                        and isinstance(ins.data, list)
                                    ):
                                        customer_id = str(
                                            ins.data[0].get("id")
                                        )
                        except Exception:
                            app.logger.exception(
                                "Supabase customer upsert failed"
                            )

                    # 2) Insert booking into `bookings` table
                    # (include resolved customer_id)
                    payload = job.copy()
                    if customer_id:
                        payload["customer_id"] = customer_id
                    res = (
                        supabase.table("bookings")
                        .insert(payload)
                        .execute()
                    )
                    if res.data and isinstance(res.data, list):
                        record = res.data[0]
                        if "id" in record:
                            job["job_id"] = str(record["id"])
                            job.update(record)
                except Exception:
                    app.logger.exception(
                        "Supabase insert failed for booking/customer"
                    )

            bookings_data.append(job)

            # Dispatch job
            dispatch_job_to_nearby_plumbers(job)

            return jsonify({
                "success": True,
                "job_id": job["job_id"],
                "booking": job
            }), 201

        # GET: return bookings from Supabase when available
        if supabase:
            try:
                res = (
                    supabase.table("bookings")
                    .select("*")
                    .order("created_at", desc=False)
                    .execute()
                )
                # res.data may be [] when no rows
                # use empty list instead of local fallback
                if hasattr(res, "data") and res.data is not None:
                    rows = res.data
                else:
                    rows = []
                return jsonify({"bookings": rows}), 200
            except Exception:
                app.logger.exception("Failed to fetch bookings from Supabase")

        # Fallback to in-memory bookings if Supabase unavailable or error
        return jsonify({"bookings": bookings_data}), 200

    except Exception as e:
        app.logger.exception("Bookings error")
        return jsonify({"error": str(e)}), 500


@app.route("/api/recommendations", methods=["GET", "OPTIONS"])
def get_recommendations():
    if request.method == "OPTIONS":
        return "", 204

    issue = (request.args.get("issue") or "").strip()
    limit = request.args.get("limit", default=6, type=int)

    plumbers = [
        {
            "id": 1,
            "name": "Ramesh Kumar",
            "rating": 4.9,
            "city": "Bangalore",
            "meta": {"skills": ["Leak Repair", "Drain Cleaning"]},
        },
        {
            "id": 2,
            "name": "Suresh Patel",
            "rating": 4.7,
            "city": "Mumbai",
            "meta": {"skills": ["Water Heater", "Bathroom Fittings"]},
        },
        {
            "id": 3,
            "name": "Arun Nair",
            "rating": 4.8,
            "city": "Chennai",
            "meta": {"skills": ["Pipe Replacement", "Emergency Repairs"]},
        },
    ]

    if issue:
        plumbers = [
            p
            for p in plumbers
            if any(issue.lower() in s.lower() for s in p["meta"]["skills"])
        ]

    result = {
        "success": True,
        "count": min(len(plumbers), limit),
        "recommendations": plumbers[:limit],
    }

    return jsonify(result)


# Plumber Events
@socketio.on('connect', namespace='/plumber')
def plumber_connect():
    print(f"Plumber connected: {request.sid}")


@socketio.on('update_location', namespace='/plumber')
def update_plumber_location(data):
    try:
        plumber_id = str(data['plumber_id'])
        lat = float(data['lat'])
        lng = float(data['lng'])

        if redis_client:
            redis_client.geoadd(ONLINE_PLUMBERS_KEY, lng, lat, plumber_id)
            redis_client.hset(PLUMBER_SOCKET_MAP, plumber_id, request.sid)
            join_room(f"plumber_{plumber_id}")

        # Forward to customer if active job
        for job_id, info in active_jobs.items():
            if info['plumber_id'] == plumber_id:
                socketio.emit('plumber_location_update', {
                    'job_id': job_id,
                    'lat': lat,
                    'lng': lng
                }, room=info['customer_room'])

        emit('location_updated', {'status': 'success'})
    except Exception as e:
        emit('error', {'message': str(e)})


@socketio.on('accept_job', namespace='/plumber')
def handle_accept_job(data):
    try:
        job_id = str(data['job_id'])
        plumber_id = str(data['plumber_id'])
        plumber_name = data.get('plumber_name', 'Plumber')

        if job_id in job_accepted_by:
            emit('job_already_accepted')
            return

        job_accepted_by[job_id] = plumber_id
        customer_room = f"customer_{job_id}"
        active_jobs[job_id] = {
            'plumber_id': plumber_id,
            'plumber_name': plumber_name,
            'customer_room': customer_room
        }

        socketio.emit('plumber_accepted', {
            'job_id': job_id,
            'plumber_name': plumber_name
        }, room=customer_room)

        socketio.emit('job_taken', {'job_id': job_id}, namespace='/plumber')

        emit('job_accepted_success')
        # persist acceptance to Supabase bookings table (non-blocking)
        if supabase:
            try:
                supabase.table('bookings').update({
                    'status': 'accepted',
                    'plumber_id': plumber_id
                }).eq('id', job_id).execute()
            except Exception:
                app.logger.exception(
                    'Failed to update booking status on accept'
                )
    except Exception as e:
        emit('error', {'message': str(e)})


@socketio.on('go_offline', namespace='/plumber')
def plumber_go_offline(data):
    try:
        plumber_id = str(data['plumber_id'])
        if redis_client:
            redis_client.zrem(ONLINE_PLUMBERS_KEY, plumber_id)
            redis_client.hdel(PLUMBER_SOCKET_MAP, plumber_id)
    except Exception:
        pass


# Customer Events
@socketio.on('connect', namespace='/customer')
def customer_connect():
    print(f"Customer connected: {request.sid}")


@socketio.on('join_job_tracking', namespace='/customer')
def customer_join_tracking(data):
    job_id = str(data.get('job_id', ''))
    if not job_id:
        return
    room = f"customer_{job_id}"
    join_room(room)

    if job_id in active_jobs:
        emit('plumber_accepted', {
            'job_id': job_id,
            'plumber_name': active_jobs[job_id]['plumber_name']
        })


# FIXED DISPATCH FUNCTION (works with old Redis)
def dispatch_job_to_nearby_plumbers(job):
    try:
        lat = job.get('customer_lat')
        lng = job.get('customer_lng')
        job_id = job['job_id']

        if not redis_client or not lat or not lng:
            print("Broadcasting job (no Redis/geo)")
            socketio.emit('new_job', job, namespace='/plumber')
            return

        # Use GEORADIUS for older Redis
        nearby = redis_client.georadius(
            ONLINE_PLUMBERS_KEY,
            longitude=lng,
            latitude=lat,
            radius=15,
            unit='km',
            count=20
        )

        if not nearby:
            print("No nearby - broadcasting")
            socketio.emit('new_job', job, namespace='/plumber')
            return

        plumber_ids = [p.decode('utf-8') for p in nearby]
        for plumber_id in plumber_ids:
            if job_id not in job_accepted_by:
                room = f"plumber_{plumber_id}"
                socketio.emit('new_job', job, room=room, namespace='/plumber')
                print(f"Job {job_id} → plumber {plumber_id}")
                # record plumber notification in history table (non-blocking)
                if supabase:
                    try:
                        job_keys = (
                            "job_id",
                            "status",
                            "customer_id",
                            "issue",
                            "created_at",
                        )
                        history_row = {
                            "plumber_id": plumber_id,
                            "job_id": job_id,
                            "event": "notified",
                            "meta": {
                                "job": {
                                    k: job.get(k) for k in job_keys
                                }
                            },
                        }
                        supabase.table(
                            "plumber_history"
                        ).insert(history_row).execute()
                    except Exception:
                        # don't interrupt dispatch for DB errors
                        print(
                            f"plumber_history insert failed for "
                            f"plumber {plumber_id}"
                        )

    except Exception as e:
        print(f"Dispatch error: {e}")
        socketio.emit('new_job', job, namespace='/plumber')  # Fallback


# Background worker: periodically re-dispatch pending/assigned jobs
def reenqueue_pending_jobs(poll_interval=30, throttle_seconds=60):
    print('Starting pending-job re-enqueue worker')
    while True:
        try:
            if not supabase:
                time.sleep(poll_interval)
                continue

            res = supabase.table('bookings').select('*').execute()
            rows = res.data if (hasattr(res, 'data') and res.data) else []

            now_ts = int(time.time())
            for row in rows:
                try:
                    status = (row.get('status') or '').lower()
                    job_id = str(row.get('id') or row.get('job_id'))
                    # consider pending or assigned jobs for re-dispatch
                    if status in ('pending', 'assigned'):
                        # throttle using Redis so we don't spam
                        last_key = f"last_dispatched:{job_id}"
                        last = None
                        if redis_client:
                            try:
                                last = redis_client.get(last_key)
                                if last:
                                    last = int(last)
                            except Exception:
                                last = None

                        if last and (now_ts - last) < throttle_seconds:
                            continue

                        # build job dict expected by dispatcher
                        job = dict(row)
                        # keep old field name compatibility
                        if 'id' in row and 'job_id' not in job:
                            job['job_id'] = str(row.get('id'))

                        dispatch_job_to_nearby_plumbers(job)

                        if redis_client:
                            try:
                                redis_client.set(last_key, now_ts)
                            except Exception:
                                pass
                except Exception:
                    continue

        except Exception as e:
            print('Re-enqueue worker error:', e)

        time.sleep(poll_interval)


# Debug endpoint for bookings token (used by frontend dev/debug tooling)
@app.route('/api/bookings/debug/token', methods=['GET', 'OPTIONS'])
def bookings_debug_token():
    if request.method == 'OPTIONS':
        return '', 200

    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return jsonify({'error': 'Invalid auth header'}), 401

    token = auth.split(' ', 1)[1].strip()
    return jsonify({'token': token}), 200


@app.route('/api/contact/send', methods=['POST', 'OPTIONS'])
def contact_send():
    if request.method == 'OPTIONS':
        return '', 200

    data = request.get_json() or {}
    if not data:
        return jsonify({'success': False, 'error': 'no data'}), 400

    # persist to Supabase if available (non-blocking)
    if supabase:
        try:
            # Supabase table is named `contact_messages` (plural)
            supabase.table("contact_messages").insert(data).execute()
        except Exception:
            # Log but don't fail if table missing or other errors
            app.logger.exception(
                "Supabase insert failed for contact (table may be "
                "missing or error occurred)"
            )

    return jsonify({'success': True}), 201


@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "message": "PlumbLink API running",
        "routes": [
            "/api/bookings",
            "/api/recommendations",
            "/api/bookings/debug/token"
        ]
    }), 200


if __name__ == "__main__":
    print("PlumbLink Server Starting")
    print("http://127.0.0.1:5000")
    socketio.run(app, debug=True, port=5000, host="0.0.0.0")
