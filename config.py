import os
from dotenv import load_dotenv


def load_config():
    load_dotenv()
    return {
        "SECRET_KEY": os.getenv("SECRET_KEY", "change-me"),
        "SENDER_DEFAULT": os.getenv("SENDER_DEFAULT", "no-reply@example.com"),
    "SCHED_INTERVAL": int(os.getenv("SCHED_INTERVAL", "60")),
    }


# convenience top-level symbols
PORT = int(os.getenv("PORT", os.getenv("FLASK_RUN_PORT", "5000")))
