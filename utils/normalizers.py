from typing import Optional
import re
from datetime import datetime


def normalize_phone(raw: Optional[str]) -> Optional[str]:
    if not raw or not isinstance(raw, str):
        return None
    digits = re.sub(r"\D", "", raw)
    if not digits:
        return None
    # If starts with country code like 55, keep; otherwise assume BR (55)
    if len(digits) <= 11:
        # local: add country code
        digits = '55' + digits
    return f'+{digits}'


def normalize_date(raw: Optional[str]) -> Optional[str]:
    if not raw or not isinstance(raw, str):
        return None
    raw = raw.strip()
    # common patterns: DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.date().isoformat()
        except Exception:
            continue
    # try parsing loose day/month/year with dots or spaces
    digits = re.sub(r"[^0-9]", " ", raw).split()
    if len(digits) == 3:
        d, m, y = digits
        try:
            dt = datetime(int(y), int(m), int(d))
            return dt.date().isoformat()
        except Exception:
            pass
    return None


def normalize_cpf(raw: Optional[str]) -> Optional[str]:
    if not raw or not isinstance(raw, str):
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 11:
        return None
    if not _validate_cpf_digits(digits):
        return None
    # format as 000.000.000-00
    return f"{digits[0:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:11]}"


def _validate_cpf_digits(d: str) -> bool:
    # CPF checksum validation
    if len(d) != 11:
        return False
    if d == d[0] * 11:
        return False
    try:
        nums = [int(x) for x in d]
    except Exception:
        return False
    # first check digit
    s = sum((10 - i) * nums[i] for i in range(9))
    r = s % 11
    v1 = 0 if r < 2 else 11 - r
    if nums[9] != v1:
        return False
    # second check digit
    s = sum((11 - i) * nums[i] for i in range(10))
    r = s % 11
    v2 = 0 if r < 2 else 11 - r
    if nums[10] != v2:
        return False
    return True
