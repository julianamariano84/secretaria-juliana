from flask import Flask, request, jsonify
import os
from config import load_config, PORT
from webhook.handler import bp as webhook_bp, handle_webhook
from scheduler.agenda import init_scheduler, schedule_consultation
from messaging.sender import send_text
from utils.validators import is_valid_phone


def create_app():
    app = Flask("SecretariaJuliana")
    app.config.update(load_config())
    app.register_blueprint(webhook_bp)
    init_scheduler(app)

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"})

    @app.route("/api/send", methods=["POST"])
    def api_send():
        data = request.get_json(silent=True) or {}
        phone = data.get("phone")
        message = data.get("message")

        if not phone or not message:
            return jsonify({"error": "phone e message são obrigatórios"}), 400
        if not is_valid_phone(phone):
            return jsonify({"error": "Número de telefone inválido"}), 400

        result = send_text(phone, message)
        return jsonify({"success": True, "result": result})

    @app.route("/api/secretaria/schedule", methods=["POST"])
    def api_schedule():
        data = request.get_json(silent=True) or {}
        required_fields = ["name", "phone", "date", "time"]
        if not all(data.get(field) for field in required_fields):
            return jsonify({"error": "name, phone, date e time são obrigatórios"}), 400
        if not is_valid_phone(data.get("phone", "")):
            return jsonify({"error": "Número de telefone inválido"}), 400

        result = schedule_consultation(data)
        return jsonify({"success": True, "result": result})

    @app.route("/webhook", methods=["POST"])
    def webhook():
        payload = request.get_json(silent=True) or {}
        note = handle_webhook(payload)
        return jsonify({"ok": True, "note": note}), 200

    # debug: list pending registrations when debug enabled
    if os.getenv('DEBUG_WEBHOOK') == '1':
        @app.route('/admin/registrations', methods=['GET'])
        def admin_regs():
            from webhook.registrations import list_pending
            return jsonify({'pending': list_pending()})

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=PORT, debug=True)