from flask import Blueprint, request, jsonify, current_app
from datetime import datetime

from app.extensions import supabase

contact_bp = Blueprint('contact', __name__, url_prefix='/api/contact')

# Fallback in-memory storage if Supabase table doesn't exist
_MESSAGES_FALLBACK = []


@contact_bp.route('/send', methods=['POST'])
def send_message():
    """Handle contact form submission and save to Supabase or fallback."""
    try:
        data = request.get_json()

        # Validate required fields
        if (not data.get('name') or not data.get('email')
                or not data.get('message')):
            return jsonify({
                'success': False,
                'error': 'All fields are required'
            }), 400

        # Validate email format (basic)
        email = data.get('email')
        if '@' not in email or '.' not in email.split('@')[1]:
            return jsonify({
                'success': False,
                'error': 'Invalid email format'
            }), 400

        message_data = {
            'name': data.get('name'),
            'email': email,
            'message': data.get('message'),
            'created_at': datetime.utcnow().isoformat(),
        }

        # Try to save to Supabase
        saved_to_db = False
        if supabase:
            try:
                response = (
                    supabase.table('contact_messages')
                    .insert(message_data)
                    .execute()
                )
                if not getattr(response, 'error', None):
                    saved_to_db = True
                    current_app.logger.info(
                        f"✅ Contact message saved to Supabase: "
                        f"{data.get('name')} ({email})"
                    )
                else:
                    current_app.logger.warning(
                        f"Supabase save failed: {response.error}. "
                        "Using fallback storage."
                    )
            except Exception as exc:
                current_app.logger.warning(
                    f"Failed to save to Supabase: {exc}. "
                    "Using fallback storage."
                )

        # Fallback: save to memory if DB failed
        if not saved_to_db:
            _MESSAGES_FALLBACK.append(message_data)
            current_app.logger.info(
                f"💾 Contact message saved to fallback storage: "
                f"{data.get('name')} ({email})"
            )

        # Log to console for visibility
        current_app.logger.info(
            f"📧 New contact: {data.get('name')} | {email} | "
            f"{data.get('message')[:50]}..."
        )

        return jsonify({
            'success': True,
            'message': ('Your message has been sent successfully! '
                        'We will respond shortly.'),
            'storage': 'database' if saved_to_db else 'fallback'
        }), 200

    except Exception as e:
        current_app.logger.error(f"Contact form error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@contact_bp.route('/messages', methods=['GET'])
def get_messages():
    """Get all contact messages (tries Supabase first, then fallback)."""
    try:
        messages = []
        source = 'unknown'

        # Try Supabase first
        if supabase:
            try:
                response = (
                    supabase.table('contact_messages')
                    .select('*')
                    .order('created_at', desc=True)
                    .execute()
                )

                if not getattr(response, 'error', None):
                    messages = response.data or []
                    source = 'supabase'
                    current_app.logger.info(
                        f"Retrieved {len(messages)} messages from Supabase"
                    )
                else:
                    current_app.logger.warning(
                        f"Supabase query failed: {response.error}. "
                        "Using fallback."
                    )
            except Exception as exc:
                current_app.logger.warning(
                    f"Supabase fetch error: {exc}. Using fallback."
                )

        # Fallback to in-memory
        if not messages and _MESSAGES_FALLBACK:
            messages = _MESSAGES_FALLBACK
            source = 'fallback'
            current_app.logger.info(
                f"Retrieved {len(messages)} messages from fallback storage"
            )

        return jsonify({
            'success': True,
            'count': len(messages),
            'source': source,
            'messages': messages
        }), 200
    except Exception as e:
        current_app.logger.error(f"Get messages error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
