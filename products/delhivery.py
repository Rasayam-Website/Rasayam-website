"""
Delhivery API Integration Service for Rasayam.

Endpoints used:
  - Pincode Serviceability: /c/api/pin-codes/json/
  - Shipment Tracking:      /api/v1/packages/json/
  - Order Creation:         /api/cmu/create.json

Authentication: Token-based header  →  Authorization: Token <API_KEY>
"""

import json
import logging
import re

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
DELHIVERY_BASE_URL = getattr(
    settings, 'DELHIVERY_BASE_URL', 'https://track.delhivery.com'
)
DELHIVERY_API_TOKEN = getattr(settings, 'DELHIVERY_API_TOKEN', '')
DELHIVERY_TIMEOUT = 15  # seconds


def _headers():
    """Common auth headers for every Delhivery request."""
    return {
        'Authorization': f'Token {DELHIVERY_API_TOKEN}',
        'Content-Type': 'application/json',
    }


# ── 1. Pincode Serviceability ────────────────────────────────────────────────

def check_pincode_serviceability(pincode: str) -> dict:
    """
    Check whether Delhivery services a given pincode.

    Returns a dict like:
      {
        'serviceable': True/False,
        'prepaid': True/False,
        'cod': True/False,
        'city': 'Mumbai',
        'state': 'Maharashtra',
        'district': 'Mumbai',
        'estimated_days': '3-5',
        'raw': {…}  # full API response for debugging
      }
    """
    cache_key = f'delhivery_pin_{pincode}'
    cached = cache.get(cache_key)
    if cached:
        return cached

    url = f'{DELHIVERY_BASE_URL}/c/api/pin-codes/json/'
    try:
        resp = requests.get(
            url,
            headers=_headers(),
            params={'filter_codes': pincode},
            timeout=DELHIVERY_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.error('Delhivery pincode check failed for %s: %s', pincode, exc)
        return {'serviceable': False, 'error': str(exc)}

    delivery_codes = data.get('delivery_codes', [])
    if not delivery_codes:
        result = {
            'serviceable': False,
            'city': '',
            'state': '',
            'district': '',
            'prepaid': False,
            'cod': False,
            'estimated_days': '',
            'raw': data,
        }
        cache.set(cache_key, result, 86400)  # cache 24 h
        return result

    info = delivery_codes[0].get('postal_code', {})
    result = {
        'serviceable': True,
        'city': info.get('city', ''),
        'state': info.get('state_code', ''),
        'district': info.get('district', ''),
        'prepaid': info.get('pre_paid', 'N') == 'Y',
        'cod': info.get('cod', 'N') == 'Y',
        'estimated_days': info.get('max_days', '5-7'),
        'max_amount': info.get('max_amount', ''),
        'raw': data,
    }
    cache.set(cache_key, result, 86400)
    return result


# ── 2. Shipment Tracking ─────────────────────────────────────────────────────

def track_shipment(waybill: str) -> dict:
    """
    Track a single shipment by its Delhivery waybill number.

    Returns a dict like:
      {
        'success': True/False,
        'waybill': '…',
        'status': 'In Transit',
        'status_detail': 'Package picked up from seller',
        'origin': 'Agra',
        'destination': 'Mumbai',
        'estimated_delivery': '2026-09-28',
        'scans': [{…}, …],   # chronological scan events
        'raw': {…},
      }
    """
    url = f'{DELHIVERY_BASE_URL}/api/v1/packages/json/'
    try:
        resp = requests.get(
            url,
            headers=_headers(),
            params={'waybill': waybill},
            timeout=DELHIVERY_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.error('Delhivery tracking failed for %s: %s', waybill, exc)
        return {'success': False, 'error': str(exc)}

    shipment_data = data.get('ShipmentData', [])
    if not shipment_data:
        return {
            'success': False,
            'error': 'No shipment data found for this waybill.',
            'raw': data,
        }

    shipment = shipment_data[0].get('Shipment', {})
    status_obj = shipment.get('Status', {})
    scans_raw = shipment.get('Scans', [])

    scans = []
    for scan_entry in scans_raw:
        scan_info = scan_entry.get('ScanDetail', {})
        scans.append({
            'timestamp': scan_info.get('ScanDateTime', ''),
            'activity': scan_info.get('Instructions', ''),
            'location': scan_info.get('ScannedLocation', ''),
            'status': scan_info.get('Scan', ''),
            'status_detail': scan_info.get('StatusDetail', ''),
        })

    return {
        'success': True,
        'waybill': waybill,
        'status': status_obj.get('Status', ''),
        'status_detail': status_obj.get('StatusType', ''),
        'origin': shipment.get('Origin', ''),
        'destination': shipment.get('Destination', ''),
        'estimated_delivery': shipment.get('ExpectedDeliveryDate', ''),
        'pickup_date': shipment.get('PickUpDate', ''),
        'delivered_date': shipment.get('DeliveredDate', ''),
        'consignee_name': (
            shipment.get('Consignee', {}).get('Name', '')
            if isinstance(shipment.get('Consignee'), dict)
            else ''
        ),
        'ref_id': shipment.get('ReferenceNo', ''),
        'scans': scans,
        'raw': data,
    }


# ── 4. Packing Slip ─────────────────────────────────────────────────────────

def get_packing_slip(waybills: str) -> dict:
    """Fetch packing slip data for one or multiple waybills (comma separated)."""
    url = f'{DELHIVERY_BASE_URL}/api/p/packing_slip'
    try:
        resp = requests.get(
            url,
            headers=_headers(),
            params={'wbns': waybills},
            timeout=DELHIVERY_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.error('Delhivery packing slip failed for %s: %s', waybills, exc)
        return {'packages_found': 0, 'packages': [], 'error': str(exc)}
