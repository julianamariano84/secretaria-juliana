"""
Quick probe for Z-API /send-text variants.
Usage (PowerShell):
  python .\scripts\zapi_quick_probe.py --url "https://.../send-text" --token TOKEN --phone 5522988045181

This script will try a small focused set of payloads and header placements and print concise results.
"""
import argparse
import json
import sys
import requests


VARIANTS = [
    # no extra headers
    (None, lambda phone, text: {"phone": phone, "message": text}, "phone+message"),
    (None, lambda phone, text: {"number": phone, "message": text}, "number+message"),
    (None, lambda phone, text: {"to": f"{phone}@c.us", "message": text}, "to@c.us+message"),
    (None, lambda phone, text: {"chatId": f"{phone}@c.us", "body": text}, "chatId+body"),
    (None, lambda phone, text: {"to": phone, "type": "text", "text": {"body": text}}, "to+type+text_obj"),
    # Authorization Bearer
    ("auth", lambda phone, text: {"phone": phone, "message": text}, "auth:phone+message"),
    ("client", lambda phone, text: {"phone": phone, "message": text}, "clienttoken:phone+message"),
]


def try_variant(url, token, phone, variant, text):
    header_mode, payload_fn, label = variant
    headers = {"Content-Type": "application/json"}
    if header_mode == "auth":
        headers["Authorization"] = f"Bearer {token}"
    elif header_mode == "client":
        headers["Client-Token"] = token

    # If token is meant in path, caller should provide url that already contains /token/<token>/send-text
    payload = payload_fn(phone, text)
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
    except Exception as e:
        return label, None, None, str(e)

    # Try to decode JSON, fallback to text
    try:
        body = r.json()
    except Exception:
        body = r.text

    return label, r.status_code, body, None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True, help="Full send-text URL (include token in path if desired)")
    p.add_argument("--token", required=True, help="Instance token (used only for header variants)")
    p.add_argument("--phone", required=True, help="Phone number like 5522988045181")
    p.add_argument("--text", default="Teste diagnostico - quick probe", help="Message text")
    args = p.parse_args()

    print("Z-API quick probe\nURL:", args.url)
    print("Phone:", args.phone)
    print("Token: (hidden)")
    print()

    results = []
    for i, v in enumerate(VARIANTS, start=1):
        label, status, body, err = try_variant(args.url, args.token, args.phone, v, args.text)
        print(f"== TRY #{i}: {label} ==")
        if err:
            print("ERROR:", err)
        else:
            print("Status:", status)
            if isinstance(body, (dict, list)):
                print(json.dumps(body, ensure_ascii=False, indent=2))
            else:
                print(body)
        print()
        results.append((label, status, body, err))

    # Print summary
    print("All attempts finished. Summary:")
    for label, status, body, err in results:
        s = status if status is not None else "ERR"
        note = "err" if err else ("ok" if status and 200 <= int(status) < 300 else "fail")
        print(f"- {label}: {s} ({note})")


if __name__ == '__main__':
    main()
