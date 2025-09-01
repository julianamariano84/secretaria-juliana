import re

def is_valid_email(addr: str) -> bool:
    if not addr or not isinstance(addr, str):
        return False
    return re.match(r"[^@]+@[^@]+\.[^@]+", addr) is not None

def is_valid_phone(phone: str) -> bool:
    if not phone or not isinstance(phone, str):
        return False
    # Accept digits, optional + and spaces/dashes; require 8-15 digits
    digits = re.sub(r"\D", "", phone)
    return 8 <= len(digits) <= 15
