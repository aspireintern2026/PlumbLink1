from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import create_access_token


def hash_password(p):
    return generate_password_hash(p)


def verify_password(h, p):
    return check_password_hash(h, p)


def generate_token(payload, exp=1440):
    """
    Generate a Flask-JWT-Extended compatible token.
    The 'id' in payload becomes the token identity (subject).
    """
    user_id = payload.get('id')
    return create_access_token(identity=user_id, expires_delta=False)
