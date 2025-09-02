from flask import Blueprint, jsonify, request
import os
import logging
import time
from .registrations import append_response, get_pending, create_pending
from .registrations import get_last_history, get_last_sent_question, set_last_sent_question
from .registrations import get_greeting_sent, mark_greeting_sent
from .registrations import get_last_outbound
from .registrations import apply_answers, mark_payment_confirmed, set_scheduling_status

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


def _maybe_send_text(phone: str, message: str):
    """Send only when QUIET_MODE != 1; otherwise, log and skip."""
    if os.getenv('QUIET_MODE', '0') == '1':
        try:
            log.info("QUIET_MODE=1 -> skipping outbound to %s: %s", phone, message)
        except Exception:
            pass
        return {"to": phone, "message": message, "status": "skipped_quiet_mode"}
    return send_text(phone, message)

bp = Blueprint("webhook", __name__, url_prefix="/webhook")

# Anti-loop/anti-spam guards
# - IGNORE_FROM_ME: ignora callbacks de mensagens enviadas pela própria instância
# - SPAM_GUARD_SECONDS: janela curta para evitar múltiplas respostas ao mesmo texto
IGNORE_FROM_ME = os.getenv('IGNORE_FROM_ME', '1') == '1'
SPAM_GUARD_SECONDS = int(os.getenv('SPAM_GUARD_SECONDS', '20'))
_LAST_SEEN = {}
_LAST_SENT_QUESTION = {}
_LAST_SENT_AT = {}
# Track recently seen provider message IDs to suppress echoes
_SEEN_MSG_IDS = {}


def _normalize_text(s: str) -> str:
    try:
        return ' '.join((s or '').split()).casefold()
    except Exception:
        return s or ''


def _is_non_chat_event(payload: dict) -> bool:
    """Heuristic: return True for status/ack events that should not trigger replies."""
    try:
        if not isinstance(payload, dict):
            return True
        # Meta/WhatsApp style statuses
        if isinstance(payload.get('statuses'), list):
            return True
        # Common top-level event/status fields
        evt = (payload.get('event') or payload.get('type') or '').lower()
        if evt in ('status', 'ack', 'message_ack', 'delivered', 'read', 'sent'):
            return True
        if payload.get('status') in ('sent', 'delivered', 'read'):
            return True
        # Z-API/others nested message type
        if isinstance(payload.get('message'), dict):
            mt = (payload['message'].get('type') or '').lower()
            if mt and mt not in ('text', 'chat', 'message'):
                return True
        # explicit delivery status hints
        if any(k in payload for k in ('messageStatus', 'acknowledged', 'ackCode', 'delivery')):
            return True
    except Exception:
        return False
    return False


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

    # Drop delivery/status callbacks early
    if _is_non_chat_event(payload):
        return jsonify({"ok": True, "ignored": "non_chat_event"}), 200

    # Ignore messages that were sent by ourselves when provider flags them
    try:
        from_me = False
        if isinstance(payload.get('message'), dict):
            m = payload['message']
            from_me = bool(m.get('fromMe') or m.get('from_me') or (isinstance(m.get('key'), dict) and m.get('key', {}).get('fromMe')))
        from_me = from_me or bool(payload.get('fromMe') or payload.get('from_me'))
        if IGNORE_FROM_ME and from_me:
            return jsonify({"ok": True, "ignored": "fromMe"}), 200
    except Exception:
        pass

    # Optional inbound blocklist via BLOCK_PHONES env
    try:
        bl_raw = os.getenv('BLOCK_PHONES', '')
        block = {(''.join(ch for ch in p if ch.isdigit())) for p in bl_raw.replace(';', ',').split(',') if p.strip()}
    except Exception:
        block = set()

    # try common shapes
    phone = None
    text = None

    # Z-API common shapes
    if 'message' in payload and isinstance(payload['message'], dict):
        msg = payload['message']
        phone = msg.get('from') or msg.get('sender') or msg.get('author')
        text = msg.get('text') or msg.get('body') or msg.get('content')
        # capture provider message id if present
        msg_id = msg.get('id') or msg.get('messageId') or msg.get('msgId') or msg.get('key', {}).get('id')
    else:
        msg_id = payload.get('id') or payload.get('messageId')

    # fallback shapes
    phone = phone or payload.get('from') or payload.get('phone') or payload.get('sender')
    text = text or payload.get('text') or payload.get('message') or payload.get('body') or payload.get('content')

    # normalize phone (remove spaces) and digits for checks
    if isinstance(phone, str):
        phone = phone.strip()
    phone_digits = ''.join(ch for ch in (phone or '') if ch.isdigit())

    if not phone or not text:
        return jsonify({"ok": False, "error": "missing phone or text", "payload": payload}), 400

    # drop immediately if phone is blocked
    if block and phone_digits in block:
        return jsonify({"ok": True, "ignored": "blocked_phone"}), 200

    log.info("inbound message from %s: %s", phone, text)

    # Anti-spam and echo suppression
    try:
        now = int(time.time())
        # provider echo suppression by message id
        if msg_id:
            last_id = _SEEN_MSG_IDS.get(phone)
            if last_id == msg_id:
                return jsonify({"ok": True, "ignored": "echo_msgid"}), 200
            _SEEN_MSG_IDS[phone] = msg_id

        # provider echo suppression by matching last outbound text within TTL
        try:
            echo_ttl = int(os.getenv('ECHO_SUPPRESS_SECONDS', '120'))
        except Exception:
            echo_ttl = 120
        if echo_ttl > 0:
            last_out = get_last_outbound(phone)
            if last_out:
                last_text_norm = _normalize_text(last_out.get('text') or '')
                cur_text_norm = _normalize_text(text)
                if last_text_norm and last_text_norm == cur_text_norm and (now - int(last_out.get('ts') or 0)) < echo_ttl:
                    return jsonify({"ok": True, "ignored": "echo_match_outbound"}), 200

        # Anti-spam window: ignore duplicate (same phone+text) within seconds
        last = _LAST_SEEN.get(phone)
        if last and _normalize_text(last.get('text') or '') == _normalize_text(text) and (now - int(last.get('ts', 0))) < SPAM_GUARD_SECONDS:
            return jsonify({"ok": True, "ignored": "duplicate_window"}), 200
        _LAST_SEEN[phone] = {"text": text, "ts": now}
    except Exception:
        pass

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
                    sent_any = False
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
                            # last inbound from store and last sent question (cross-process)
                            last_entry = get_last_history(phone)
                            last = last_entry.get('text') if last_entry else None
                            last_q_persisted = get_last_sent_question(phone)
                            # avoid re-sending same question we already sent very recently
                            last_q = _LAST_SENT_QUESTION.get(phone) or last_q_persisted
                            # simple per-phone backoff for prompts (avoid sending too fast)
                            now = int(time.time())
                            last_at = _LAST_SENT_AT.get(phone) or 0
                            backoff = int(os.getenv('PROMPT_BACKOFF_SECONDS', '10'))
                            if question and question != last and question != last_q and (now - last_at) >= backoff:
                                try:
                                    log.info("sending question to %s: %s", phone, question)
                                    _maybe_send_text(phone, question)
                                    _LAST_SENT_QUESTION[phone] = question
                                    _LAST_SENT_AT[phone] = now
                                    try:
                                        set_last_sent_question(phone, question)
                                    except Exception:
                                        pass
                                    sent_any = True
                                except Exception:
                                    log.exception("failed to send question to %s", phone)
                            break
                    # also try to send a friendly greeting via the model (only on first contact and at most once)
                    if first_contact and os.getenv('DISABLE_GREETING','0') != '1' and generate_greeting_and_action and not sent_any and not get_greeting_sent(phone):
                        try:
                            ga = generate_greeting_and_action(text, first_contact=first_contact)
                            if isinstance(ga, dict) and ga.get('greeting'):
                                try:
                                    log.info("sending model greeting to %s: %s", phone, ga.get('greeting'))
                                    _maybe_send_text(phone, ga.get('greeting'))
                                    try:
                                        mark_greeting_sent(phone)
                                    except Exception:
                                        pass
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
                                            _maybe_send_text(phone, f"Para finalizar o agendamento, por favor efetue o pagamento: {url}")
                                        except Exception:
                                            log.exception("failed to send payment link to %s", phone)
                                        # anticipate scheduling preferences after payment
                                        try:
                                            set_scheduling_status(phone, 'awaiting_time')
                                            _maybe_send_text(phone, "Depois do pagamento, me diga os melhores dias/horários para a consulta e eu encaixo na agenda da Juliana, combinado?")
                                        except Exception:
                                            log.exception('failed to set scheduling status for %s', phone)
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
            sent_any = False
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
                    last_entry = get_last_history(phone)
                    last = last_entry.get('text') if last_entry else None
                    last_q_persisted = get_last_sent_question(phone)
                    last_q = _LAST_SENT_QUESTION.get(phone) or last_q_persisted
                    now = int(time.time())
                    last_at = _LAST_SENT_AT.get(phone) or 0
                    backoff = int(os.getenv('PROMPT_BACKOFF_SECONDS', '10'))
                    if question and question != last and question != last_q and (now - last_at) >= backoff:
                        try:
                            log.info("sending question to %s: %s", phone, question)
                            _maybe_send_text(phone, question)
                            _LAST_SENT_QUESTION[phone] = question
                            _LAST_SENT_AT[phone] = now
                            try:
                                set_last_sent_question(phone, question)
                            except Exception:
                                pass
                            sent_any = True
                        except Exception:
                            log.exception("failed to send question to %s", phone)
                    break
            # model-based greeting as optional nicety (at most once per phone)
            if os.getenv('DISABLE_GREETING','0') != '1' and generate_greeting_and_action and not sent_any and not get_greeting_sent(phone):
                try:
                    ga = generate_greeting_and_action(text, first_contact=first_contact)
                    if isinstance(ga, dict) and ga.get('greeting'):
                        try:
                            log.info("sending model greeting to %s: %s", phone, ga.get('greeting'))
                            _maybe_send_text(phone, ga.get('greeting'))
                            try:
                                mark_greeting_sent(phone)
                            except Exception:
                                pass
                        except Exception:
                            log.exception("failed to send greeting to %s", phone)
                except Exception:
                    pass
    except Exception:
        pass

    return jsonify({"ok": True, "record": rec})


@bp.route('/entrada', methods=['POST'])
def entrada():
    """Portuguese alias for /webhook/inbound.

    Delegates to inbound() to ensure identical anti-loop behavior.
    """
    return inbound()


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
                _maybe_send_text(phone, "Pagamento recebido! Sua consulta foi agendada. Entraremos em contato para confirmar o horário.")
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
            # Ignore self-sent messages if provider flags them
            try:
                from_me = False
                if isinstance(payload.get('message'), dict):
                    m = payload['message']
                    from_me = bool(m.get('fromMe') or m.get('from_me'))
                from_me = from_me or bool(payload.get('fromMe') or payload.get('from_me'))
                if IGNORE_FROM_ME and from_me:
                    return {"note": "ignored fromMe"}
            except Exception:
                pass
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
                    sent_any = False
                    # prefer asking next unanswered (with backoff and dedupe like inbound)
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
                            last_q_persisted = get_last_sent_question(phone)
                            last_q = _LAST_SENT_QUESTION.get(phone) or last_q_persisted
                            now = int(time.time())
                            last_at = _LAST_SENT_AT.get(phone) or 0
                            backoff = int(os.getenv('PROMPT_BACKOFF_SECONDS', '10'))
                            if question and question != last and question != last_q and (now - last_at) >= backoff:
                                try:
                                    log.info("handle_webhook sending question to %s: %s", phone, question)
                                    _maybe_send_text(phone, question)
                                    _LAST_SENT_QUESTION[phone] = question
                                    _LAST_SENT_AT[phone] = now
                                    try:
                                        set_last_sent_question(phone, question)
                                    except Exception:
                                        pass
                                    sent_any = True
                                except Exception:
                                    log.exception("handle_webhook failed to send question to %s", phone)
                            break
                    # model greeting optional (at most once)
                    if os.getenv('DISABLE_GREETING','0') != '1' and generate_greeting_and_action and not sent_any and not get_greeting_sent(phone):
                        try:
                            ga = generate_greeting_and_action(text)
                            if isinstance(ga, dict) and ga.get('greeting'):
                                try:
                                    _maybe_send_text(phone, ga.get('greeting'))
                                    try:
                                        mark_greeting_sent(phone)
                                    except Exception:
                                        pass
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


@bp.route('/_last', methods=['GET'])
def _debug_last():
    # only enabled with DEBUG_ZAPI=1 and correct token
    if os.getenv('DEBUG_ZAPI') != '1':
        return jsonify({'ok': False, 'error': 'debug disabled'}), 404
    expected = os.getenv('DEBUG_TOKEN')
    provided = request.headers.get('X-Debug-Token') or request.args.get('token')
    if not expected or provided != expected:
        return jsonify({'ok': False, 'error': 'forbidden'}), 403
    try:
        from messaging.sender import get_last_debug
        data = get_last_debug() or {}
        return jsonify({'ok': True, **data})
    except Exception:
        return jsonify({'ok': False, 'error': 'unavailable'}), 500
