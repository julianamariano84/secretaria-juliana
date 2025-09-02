from flask import Blueprint, jsonify, request
import os
import logging
from .registrations import append_response, get_pending, create_pending
from .registrations import apply_answers, mark_payment_confirmed

log = logging.getLogger(__name__)

try:
    from services.openai_client import extract_registration_fields, generate_greeting_and_action
except Exception:
    extract_registration_fields = None
    generate_greeting_and_action = None

try:
    from services.infinitepay import create_payment_intent
except Exception:
    create_payment_intent = None

try:
    import messaging.sender as sender_mod
    send_text = getattr(sender_mod, 'send_text', None)
except Exception:
    send_text = None

# safe fallback send_text that only logs when real sender is missing
def _no_op_send(phone: str, message: str) -> dict:
    log.info("send_text not available (no-op): to=%s message=%s", phone, message)
    return {"to": phone, "message": message, "status": "noop"}

if send_text is None:
    send_text = _no_op_send

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
    # optional secret validation: if WEBHOOK_SECRET is set, require the header
    secret = os.getenv('WEBHOOK_SECRET')
    if secret:
        header_name = os.getenv('WEBHOOK_HEADER', 'X-Hook-Token')
        token = request.headers.get(header_name)
        if token != secret:
            log.warning("webhook auth failed from %s header=%s", request.remote_addr, header_name)
            return jsonify({"ok": False, "error": "unauthorized"}), 401

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

    log.info("inbound message from %s: %s", phone, text)

    # detect if this is the first contact from this phone
    existing = get_pending(phone)
    first_contact = existing is None

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
            # Optionally generate and send a follow-up greeting/action.
            # Prefer asking the next missing question from the pending record
            try:
                if rec:
                    # determine next unanswered question
                    for q in rec.get('questions', []):
                        if q not in rec.get('answers', {}):
                            qmap = {
                                'name': 'Qual seu nome completo?',
                                'dob': 'Qual sua data de nascimento (dd/mm/aaaa)?',
                                'cpf': 'Qual seu CPF?',
                                'address': 'Qual seu endereço?',
                                'confirm': 'Você confirma que deseja se cadastrar? (sim/não)'
                            }
                            question = qmap.get(q)
                            # avoid re-sending same question if it's the last history entry
                            last = None
                            try:
                                last = (rec.get('history') or [])[-1].get('text') if rec.get('history') else None
                            except Exception:
                                last = None
                            if question and question != last:
                                try:
                                    log.info("sending question to %s: %s", phone, question)
                                    send_text(phone, question)
                                except Exception:
                                    log.exception("failed to send question to %s", phone)
                            break
                    # also try to send a friendly greeting via the model if available
                    if generate_greeting_and_action:
                        try:
                            ga = generate_greeting_and_action(text, first_contact=first_contact)
                            if isinstance(ga, dict) and ga.get('greeting'):
                                try:
                                    log.info("sending model greeting to %s: %s", phone, ga.get('greeting'))
                                    send_text(phone, ga.get('greeting'))
                                except Exception:
                                    log.exception("failed to send greeting to %s", phone)
                        except Exception:
                            log.exception('generate_greeting_and_action failed')

                    # If registration is complete and user confirmed, create payment
                    try:
                        answers = rec.get('answers', {})
                        confirmed = answers.get('confirm')
                        if rec.get('status') == 'complete' and confirmed in (True, 'sim', 'Sim', 'SIM', 'yes', '1'):
                            # create a payment using InfinitePay if available
                            if create_payment_intent:
                                try:
                                    # build an order id and result_url so deeplink mode can return a link
                                    import uuid
                                    oid = str(uuid.uuid4())
                                    result_url = os.getenv('WEBHOOK_PUBLIC_URL', '').rstrip('/') + '/webhook/payment-callback'
                                    pay = create_payment_intent(phone, amount_cents=15000, description='Consulta médica', order_id=oid, result_url=result_url)
                                    # try to extract a payment url from provider response
                                    url = pay.get('payment_url') or pay.get('url') or pay.get('checkout_url')
                                    from .registrations import mark_payment_created
                                    mark_payment_created(phone, {'provider': 'infinitepay', 'raw': pay, 'url': url, 'order_id': pay.get('order_id') or oid})
                                    if url:
                                        try:
                                            send_text(phone, f"Para finalizar o agendamento, por favor efetue o pagamento: {url}")
                                        except Exception:
                                            log.exception("failed to send payment link to %s", phone)
                                except Exception:
                                    log.exception('failed to create payment for %s', phone)
                    except Exception:
                        log.exception('payment creation flow failed for %s', phone)
            except Exception:
                pass
            return jsonify({"ok": True, "record": rec, "extracted": True})
        except Exception:
            # fallback to raw append
            rec = append_response(phone, text, ts=payload.get('timestamp'))
            return jsonify({"ok": True, "record": rec, "extracted": False})

    # best-effort append when extraction not available or failed
    rec = append_response(phone, text, ts=payload.get('timestamp'))

    # generate and send greeting + next action when possible
    try:
        if rec:
            # prefer asking the next unanswered question
            for q in rec.get('questions', []):
                if q not in rec.get('answers', {}):
                    qmap = {
                        'name': 'Qual seu nome completo?',
                        'dob': 'Qual sua data de nascimento (dd/mm/aaaa)?',
                        'cpf': 'Qual seu CPF?',
                        'address': 'Qual seu endereço?',
                        'confirm': 'Você confirma que deseja se cadastrar? (sim/não)'
                    }
                    question = qmap.get(q)
                    last = None
                    try:
                        last = (rec.get('history') or [])[-1].get('text') if rec.get('history') else None
                    except Exception:
                        last = None
                    if question and question != last:
                        try:
                            log.info("sending question to %s: %s", phone, question)
                            send_text(phone, question)
                        except Exception:
                            log.exception("failed to send question to %s", phone)
                    break
            # model-based greeting as optional nicety
            if generate_greeting_and_action:
                try:
                    ga = generate_greeting_and_action(text, first_contact=first_contact)
                    if isinstance(ga, dict) and ga.get('greeting'):
                        try:
                            log.info("sending model greeting to %s: %s", phone, ga.get('greeting'))
                            send_text(phone, ga.get('greeting'))
                        except Exception:
                            log.exception("failed to send greeting to %s", phone)
                except Exception:
                    pass
    except Exception:
        pass

    return jsonify({"ok": True, "record": rec})


@bp.route('/payment-callback', methods=['GET', 'POST'])
def payment_callback():
    """Endpoint to receive InfinitePay deeplink/result callbacks.

    InfinitePay may call a deeplink/result URL with query parameters such as
    order_id, nsu, aut, card_brand, etc. We accept GET or POST and try to
    map the callback to a phone number (if provided) and mark the payment
    as confirmed.
    """
    # collect params
    params = request.args.to_dict() or request.get_json(silent=True) or {}

    # prefer phone param if present
    phone = params.get('phone') or params.get('customer_phone') or params.get('order_phone')

    try:
        if phone:
            # mark payment confirmed in registrations
            mark_payment_confirmed(phone, params)
            # notify user
            try:
                send_text(phone, "Pagamento recebido! Sua consulta foi agendada. Entraremos em contato para confirmar o horário.")
            except Exception:
                log.exception('failed to send payment confirmation to %s', phone)
            return jsonify({"ok": True, "phone": phone, "params": params})
        else:
            log.info('payment_callback received without phone: %s', params)
            return jsonify({"ok": True, "note": "no phone provided", "params": params})
    except Exception:
        log.exception('payment_callback failed')
        return jsonify({"ok": False}), 500


def handle_webhook(payload: dict) -> dict:
    # backward-compatible webhook handler used by some adapters.
    try:
        log.info("handle_webhook payload=%s", payload)
    except Exception:
        pass

    # attempt to normalize common shapes to phone/text
    phone = None
    text = None
    try:
        if not isinstance(payload, dict):
            return {"note": "invalid payload", "payload": payload}

        # common direct fields
        phone = payload.get('from') or payload.get('phone') or payload.get('sender')
        # message text could be under several keys
        text = payload.get('text') or payload.get('message') or payload.get('body') or payload.get('content')

        # Z-API sometimes wraps message inside 'message' dict with nested 'text' or 'body'
        if not text and isinstance(payload.get('message'), dict):
            m = payload.get('message')
            text = m.get('text') or m.get('body') or m.get('content')
            phone = phone or m.get('from') or m.get('author') or m.get('sender')

        # some callbacks include a nested 'data' or 'payload' with the real message
        if not text and isinstance(payload.get('data'), dict):
            d = payload.get('data')
            text = d.get('text') or d.get('body') or d.get('message')
            phone = phone or d.get('from') or d.get('sender')

        # final normalization
        if isinstance(phone, str):
            phone = phone.strip()
        if phone and text:
            # reuse the append + greeting logic from inbound
            rec = append_response(phone, text)

            # try structured extraction
            try:
                if extract_registration_fields:
                    parsed = extract_registration_fields(text)
                    if parsed and not (isinstance(parsed, dict) and parsed.get('error')):
                        try:
                            apply_answers(phone, parsed)
                            rec = get_pending(phone)
                        except Exception:
                            pass
            except Exception:
                pass

            # send next question/greeting like inbound
            try:
                if rec:
                    # prefer asking next unanswered
                    for q in rec.get('questions', []):
                        if q not in rec.get('answers', {}):
                            qmap = {
                                'name': 'Qual seu nome completo?',
                                'dob': 'Qual sua data de nascimento (dd/mm/aaaa)?',
                                'cpf': 'Qual seu CPF?',
                                'address': 'Qual seu endereço?',
                                'confirm': 'Você confirma que deseja se cadastrar? (sim/não)'
                            }
                            question = qmap.get(q)
                            last = None
                            try:
                                last = (rec.get('history') or [])[-1].get('text') if rec.get('history') else None
                            except Exception:
                                last = None
                            if question and question != last:
                                try:
                                    log.info("handle_webhook sending question to %s: %s", phone, question)
                                    send_text(phone, question)
                                except Exception:
                                    log.exception("handle_webhook failed to send question to %s", phone)
                            break
                    # model greeting optional
                    if generate_greeting_and_action:
                        try:
                            ga = generate_greeting_and_action(text)
                            if isinstance(ga, dict) and ga.get('greeting'):
                                try:
                                    send_text(phone, ga.get('greeting'))
                                except Exception:
                                    pass
                        except Exception:
                            pass
            except Exception:
                pass

            return {"note": "appended", "registration": rec}

    except Exception:
        log.exception("handle_webhook unexpected error")

    # fallback: just acknowledge receipt
    try:
        print(f"[stub] handle_webhook payload={payload}")
    except Exception:
        pass
    return {"note": "received", "payload": payload}


@bp.route('/_env', methods=['GET'])
def _debug_env():
    """Secure debug endpoint (only when DEBUG_ZAPI=1).

    Requires header 'X-Debug-Token' to match env var DEBUG_TOKEN. Returns masked
    values for ZAPI_URL, ZAP_TOKEN and CLIENT_TOKEN to help confirm deployed envs.
    """
    # only enabled when explicitly set
    if os.getenv('DEBUG_ZAPI') != '1':
        return jsonify({'ok': False, 'error': 'debug disabled'}), 404

    expected = os.getenv('DEBUG_TOKEN')
    provided = request.headers.get('X-Debug-Token') or request.args.get('token')
    if not expected or provided != expected:
        return jsonify({'ok': False, 'error': 'forbidden'}), 403

    def mask(v: str):
        if not v:
            return None
        s = str(v)
        if len(s) <= 8:
            return s[:2] + '***' + s[-2:]
        return s[:4] + '...' + s[-4:]

    zurl = os.getenv('ZAPI_URL')
    ztoken = os.getenv('ZAP_TOKEN') or os.getenv('ZAPI_TOKEN')
    client = os.getenv('CLIENT_TOKEN') or os.getenv('CLIENTTOKEN')
    wh_secret = os.getenv('WEBHOOK_SECRET')
    wh_header = os.getenv('WEBHOOK_HEADER') or 'X-Hook-Token'
    token_in_url = None
    try:
        if zurl and '/token/' in zurl:
            token_in_url = zurl.split('/token/', 1)[1].split('/', 1)[0]
    except Exception:
        token_in_url = None

    return jsonify({
        'ok': True,
        'ZAPI_URL': mask(zurl),
        'ZAP_TOKEN': mask(ztoken),
        'CLIENT_TOKEN': mask(client),
    'WEBHOOK_SECRET': mask(wh_secret),
    'WEBHOOK_HEADER': wh_header,
        'token_in_url': mask(token_in_url),
    })
