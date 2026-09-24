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


# ── 3. Create Shipment Order ─────────────────────────────────────────────────

def create_shipment(order) -> dict:
    """
    Create a shipment on Delhivery for the given Django Order object.

    Returns:
      {
        'success': True/False,
        'waybill': '…',
        'error': '…',
        'raw': {…},
      }
    """
    url = f'{DELHIVERY_BASE_URL}/api/cmu/create.json'

    # Parse the shipping_address text into components
    addr_lines = order.shipping_address.split('\n') if order.shipping_address else []
    name = addr_lines[0] if len(addr_lines) > 0 else 'Customer'
    add = ', '.join(addr_lines[1:4]) if len(addr_lines) > 1 else ''
    phone_line = addr_lines[-1] if len(addr_lines) >= 1 else ''
    phone = phone_line.replace('Phone:', '').strip() if 'Phone:' in phone_line else ''

    # Extract pincode from address
    pin_match = re.search(r'\b(\d{6})\b', order.shipping_address or '')
    pincode = pin_match.group(1) if pin_match else ''

    # Build order items description
    items = order.items.all()
    product_desc = ', '.join([
        f"{item.product_name} (x{item.quantity})"
        for item in items
    ])

    shipment_payload = {
        'shipments': [{
            'name': name,
            'add': add or order.shipping_address,
            'pin': pincode,
            'city': '',
            'state': '',
            'country': 'India',
            'phone': phone,
            'order': f'RASAYAM-{order.id}',
            'payment_mode': 'Prepaid',
            'return_pin': '282007',
            'return_city': 'Agra',
            'return_phone': '8923061123',
            'return_add': 'Sai Poorna Appartment, Dushyant Nagar, Paschimpuri Road, Agra',
            'return_state': 'Uttar Pradesh',
            'return_country': 'India',
            'return_name': 'RASAYAM',
            'products_desc': product_desc[:200],
            'hsn_code': '',
            'cod_amount': '0',
            'order_date': (
                order.created_at.strftime('%Y-%m-%dT%H:%M:%S')
                if order.created_at else ''
            ),
            'total_amount': str(order.total_amount),
            'seller_add': 'Sai Poorna Appartment, Dushyant Nagar, Paschimpuri Road, Agra 282007',
            'seller_name': 'RASAYAM',
            'seller_inv': f'INV-{order.id}',
            'quantity': sum(item.quantity for item in items),
            'waybill': '',  # Delhivery auto-generates
            'shipment_width': 30,
            'shipment_height': 10,
            'weight': 500,  # grams
            'seller_gst_tin': '09ALXPA4766B2ZV',
        }]
    }

    try:
        resp = requests.post(
            url,
            headers=_headers(),
            data={
                'format': 'json',
                'data': json.dumps(shipment_payload),
            },
            timeout=DELHIVERY_TIMEOUT,
        )
        resp.raise_for_status()
        result = resp.json()
    except requests.RequestException as exc:
        logger.error('Delhivery create shipment failed for order %s: %s', order.id, exc)
        return {'success': False, 'error': str(exc)}

    # Extract waybill from response
    packages = result.get('packages', [])
    if packages:
        waybill = packages[0].get('waybill', '')
        status = packages[0].get('status', '')
        if waybill:
            return {
                'success': True,
                'waybill': waybill,
                'status': status,
                'raw': result,
            }

    return {
        'success': False,
        'error': result.get('rmk', 'Unknown error'),
        'raw': result,
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
