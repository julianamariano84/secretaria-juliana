from flask import Blueprint, jsonify, request
from .registrations import append_response, get_pending, create_pending
from .registrations import apply_answers
try:
    from services.openai_client import extract_registration_fields
except Exception:
    extract_registration_fields = None

bp = Blueprint("webhook", __name__, url_prefix="/webhook")


@bp.route("/ping", methods=["GET"])
def ping():
    return jsonify({"ok": True})


@bp.route('/inbound', methods=['POST'])
def inbound():
    """Generic inbound webhook for messaging providers.

    Expected JSON payloads vary; this handler tries to extract a phone and
    a text message from common shapes. If provider-specific mapping is
    desired, set a small adapter here.
    """
    payload = request.get_json(silent=True) or {}

    # try common shapes
    phone = None
    text = None

    # Z-API common shapes
    if 'message' in payload and isinstance(payload['message'], dict):
        msg = payload['message']
        phone = msg.get('from') or msg.get('sender') or msg.get('author')
        text = msg.get('text') or msg.get('body') or msg.get('content')

    # fallback shapes
    phone = phone or payload.get('from') or payload.get('phone') or payload.get('sender')
    text = text or payload.get('text') or payload.get('message') or payload.get('body') or payload.get('content')

    # normalize phone (remove spaces)
    if isinstance(phone, str):
        phone = phone.strip()

    if not phone or not text:
        return jsonify({"ok": False, "error": "missing phone or text", "payload": payload}), 400

    # Try structured extraction via OpenAI first (non-blocking)
    parsed = None
    if extract_registration_fields:
        try:
            parsed = extract_registration_fields(text)
        except Exception:
            parsed = None

    if parsed and not (isinstance(parsed, dict) and parsed.get('error')):
        # merge structured answers into pending registration if exists
        try:
            apply_answers(phone, parsed)
            rec = get_pending(phone)
            return jsonify({"ok": True, "record": rec, "extracted": True})
        except Exception:
            # fallback to raw append
            rec = append_response(phone, text, ts=payload.get('timestamp'))
            return jsonify({"ok": True, "record": rec, "extracted": False})

    # best-effort append when extraction not available or failed
    rec = append_response(phone, text, ts=payload.get('timestamp'))
    return jsonify({"ok": True, "record": rec})


def handle_webhook(payload: dict) -> dict:
    # backward-compatible stub
    try:
        phone = payload.get('from') or payload.get('phone')
        text = payload.get('text') or payload.get('message')
        if phone and text:
            rec = append_response(phone, text)
            return {"note": "appended", "registration": rec}
    except Exception:
        pass
    print(f"[stub] handle_webhook payload={payload}")
    return {"note": "received", "payload": payload}
