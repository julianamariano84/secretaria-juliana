"""Minimal InfinitePay API adapter used to create and check payments.

This is intentionally small and driven by environment variables:
- INFINITEPAY_API_URL: base URL for InfinitePay API (e.g. https://api.infinitepay.com.br/v1)
- INFINITEPAY_API_KEY: bearer API key

The real InfinitePay API may have different endpoints/fields; this adapter
accepts the common pattern of creating a payment and returning a payment URL
in the JSON response under keys like `payment_url` or `url`.
"""
import os
import logging
from typing import Optional, Dict, Any
import requests

logger = logging.getLogger(__name__)

API_URL = os.getenv('INFINITEPAY_API_URL')
API_KEY = os.getenv('INFINITEPAY_API_KEY')
# If INFINITEPAY_DEEPLINK_BASE is set (e.g. "infinitepaydash://infinitetap-app"),
# the adapter will generate a deeplink URL instead of calling an HTTP API.
DEEPLINK_BASE = os.getenv('INFINITEPAY_DEEPLINK_BASE')
APP_REF = os.getenv('INFINITEPAY_APP_REF', 'SecretariaApp')


def _require_config():
    if not API_URL or not API_KEY:
        raise RuntimeError('INFINITEPAY_API_URL or INFINITEPAY_API_KEY not configured')


def create_payment_intent(phone: str, amount_cents: int = 15000, description: str = 'Consulta médica', metadata: Optional[Dict[str, Any]] = None, order_id: Optional[str] = None, result_url: Optional[str] = None, payment_method: str = 'credit', installments: int = 1) -> Dict[str, Any]:
    """Create a payment intent or generate a deeplink for InfiniteTap.

    If `INFINITEPAY_DEEPLINK_BASE` is set, this will return a dict containing
    the deeplink under the `url` key and echo back order_id. Otherwise it
    attempts a POST to the configured API endpoint.
    """
    # If deeplink mode requested, just construct the deeplink and return it.
    if DEEPLINK_BASE:
        oid = order_id or f"order-{int(__import__('time').time())}"
        # InfinitePay expects amount in cents as integer string according to docs
        params = {
            'amount': str(int(amount_cents)),
            'payment_method': payment_method,
            'installments': str(int(installments)),
            'order_id': oid,
            'result_url': result_url or os.getenv('WEBHOOK_PUBLIC_URL', '').rstrip('/') + '/webhook/payment-callback',
            'app_client_referrer': APP_REF,
            'af_force_deeplink': 'true',
        }
        # include phone in metadata where helpful
        if phone:
            params['phone'] = phone
        # include optional description/metadata
        if metadata:
            # flatten small metadata fields into query params if simple
            for k, v in (metadata.items() if isinstance(metadata, dict) else []):
                try:
                    params[str(k)] = str(v)
                except Exception:
                    pass

        from urllib.parse import urlencode
        qs = urlencode(params)
        deeplink = f"{DEEPLINK_BASE}?{qs}"
        logger.info('infinitepay: generated deeplink for %s -> %s', phone, deeplink)
        return {'url': deeplink, 'order_id': oid, 'raw': params}

    # Otherwise try HTTP API if configured
    _require_config()
    url = API_URL.rstrip('/') + '/payments'
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json',
    }
    payload = {
        'amount': amount_cents,
        'currency': 'BRL',
        'description': description,
        'customer': {'phone': phone},
    }
    if metadata:
        payload['metadata'] = metadata

    try:
        logger.info('infinitepay: creating payment for %s amount=%s', phone, amount_cents)
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        logger.debug('infinitepay: create response: %s', data)
        return data
    except Exception as e:
        logger.exception('infinitepay: create_payment_intent failed: %s', e)
        raise


def get_payment_status(payment_id: str) -> Dict[str, Any]:
    _require_config()
    url = API_URL.rstrip('/') + f'/payments/{payment_id}'
    headers = {'Authorization': f'Bearer {API_KEY}'}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.exception('infinitepay: get_payment_status failed: %s', e)
        raise
