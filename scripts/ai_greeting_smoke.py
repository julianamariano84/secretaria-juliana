import os
import sys
from pathlib import Path

# ensure project root is on sys.path when running from scripts/
ROOT = str(Path(__file__).resolve().parents[1])
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.openai_client import generate_greeting_and_action

# Make sure tests don't accidentally send messages anywhere
os.environ.setdefault('QUIET_MODE', '1')

samples = [
    ("oi", True),
    ("olá, bom dia! quero marcar uma consulta para meu filho", True),
    ("meu nome é Ana Paula, nasci 03/05/2010, cpf 123.456.789-09, moro na Rua das Flores 123, confirmo", False),
]

for text, first in samples:
    out = generate_greeting_and_action(text, first_contact=first)
    print("INPUT:", text)
    print("OUTPUT:", out)
    print("-")
