from flask import Flask, request, make_response
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import Config

jwt = JWTManager()

def create_app(config_object=None):
    app = Flask(__name__)
    # allow dev frontend origin (adjust for production)
    CORS(app, resources={r"/api/*": {"origins": ["http://127.0.0.1:5500","http://localhost:5500"]}}, supports_credentials=True)

    app.config.from_object(Config)

    # Optional: Explicit preflight handler (helps in tricky cases)
    @app.before_request
    def handle_options():
        if request.method == "OPTIONS":
            origin = request.headers.get("Origin", "")
            if origin in ["http://127.0.0.1:5500", "http://localhost:5500"]:
                resp = make_response()
                resp.headers["Access-Control-Allow-Origin"] = origin
                resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS, PUT, DELETE"
                resp.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, Accept"
                return resp, 204
        return None

    # Optional: After-request (only if you want to be extra sure)
    # But flask-cors usually handles this well – can remove later
    @app.after_request
    def apply_cors(response):
        origin = request.headers.get("Origin")
        if origin and origin in ["http://127.0.0.1:5500", "http://localhost:5500"]:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "false"  # explicit false
        return response

    jwt.init_app(app)

    # Blueprints (import defensively so missing optional modules don't break startup)
    def try_register(import_path, bp_name):
        try:
            mod = __import__(import_path, fromlist=[bp_name])
            bp = getattr(mod, bp_name)
            app.register_blueprint(bp)
        except Exception as e:
            app.logger.warning("Could not register %s: %s", import_path, e)

    try_register("app.api.bookings", "bookings_bp")
    try_register("app.api.auth", "auth_bp")
    try_register("app.api.recommendations", "recommendations_bp")
    try_register("app.api.chatbot", "chatbot_bp")
    try_register("app.api.contact", "contact_bp")
    try_register("app.jobs.routes", "jobs_bp")
    try_register("app.shift.routes", "shift_bp")

    return app