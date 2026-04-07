import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "change-me-too")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL")
        or os.environ.get("SUPABASE_DB_URL")
        or None
    )
    if (
        SQLALCHEMY_DATABASE_URI
        and SQLALCHEMY_DATABASE_URI.startswith("postgres://")
    ):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace(
            "postgres://", "postgresql://", 1
        )


config = {
    "default": Config,
    "development": Config,
    "production": Config,
}

class Config:
    SECRET_KEY = 'your-super-secret-key-change-in-production'
    REDIS_URL = "redis://localhost:6379/0"  # Default local Redis
    # Add other config later if needed

