from flask import Blueprint, request, jsonify
from typing import Optional, Dict, List
import os
from config import logger
from business import get_threshold, calculate_cashflow_difference
from sheets import get_sheets_service, get_last_row
from salesforce import update_opportunity

routes = Blueprint('routes', __name__)

@routes.route('/fetch-data')
def fetch_data():
    """
    Fetches rent, purchase price and cash flow post investor from Google Sheets for a given SF opportunity ID.
    Computes:
    - 3% rent increase
    - threshold requirement based on the purchase price
    - whether current cashflow meets the threshold
    - row number so we can make a quicker update later
    """
    opp_id: Optional[str] = request.args.get('opp_id')
    logger.debug(f"Received request to fetch data for Opportunity ID: {opp_id}")
    if not opp_id:
        return 'Please provide an Opportunity ID as a query parameter: ?opp_id=...', 400

    spreadsheet_id = os.environ.get('GOOGLE_SHEET_ID')
    sheet_name = os.environ.get('GOOGLE_SHEET_NAME')
    logger.debug(f"Spreadsheet ID: {spreadsheet_id}, Sheet Name: {sheet_name}")

    if not spreadsheet_id or not sheet_name:
        logger.error("Missing GOOGLE_SHEET_ID or GOOGLE_SHEET_NAME environment variable")
        return 'Internal config error: Missing sheet ID or name', 500

    try:
        service = get_sheets_service()
        last_row = get_last_row(service, spreadsheet_id, sheet_name)

        # Data starts in row 3 due to header
        range = f"{sheet_name}!A3:BW{last_row}"
        resp = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range
        ).execute()

        rows = resp.get('values', [])

        id_to_row: Dict[str, List[str]] = {}
        row_number_map: Dict[str, int] = {}

        for i, row in enumerate(rows):
            try:
                if len(row) > 74:
                    raw_id = row[74]
                    if raw_id:
                        id_val = ''.join(raw_id.split()).lower()
                        id_to_row[id_val] = row
                        row_number_map[id_val] = i + 3  # Offset for row start at 3
                else:
                    logger.debug(f"Row {i+3} too short: only {len(row)} columns")
            except Exception as e:
                logger.error(f"Error processing row {i+3}: {e} | Row content: {row}")

        logger.debug(f"Collected {len(id_to_row)} valid rows")
        logger.debug(f"Sample IDs: {list(id_to_row.keys())[:5]}")

        normalized_opp_id = ''.join(opp_id.split()).lower()
        if normalized_opp_id not in id_to_row:
            logger.debug(f"No data found for Opportunity ID: {opp_id}")
            return f"No data found for Opportunity ID: {opp_id}", 404

        found_row = id_to_row[normalized_opp_id]
        row_number = row_number_map[normalized_opp_id]

        # Sheet column mapping
        rent_raw = found_row[18] if len(found_row) > 18 else ''
        purchase_price_raw = found_row[9] if len(found_row) > 9 else ''
        cashflow_raw = found_row[29] if len(found_row) > 29 else ''

        def parse_num(value: str) -> float:
            return float(''.join(ch for ch in value if ch in '0123456789.-')) if value else 0.0

        logger.debug(f"Parsed values - Rent: {rent_raw}, Purchase Price: {purchase_price_raw}, Cashflow: {cashflow_raw}")

        rent = parse_num(rent_raw)
        purchase_price = parse_num(purchase_price_raw)
        cashflow = parse_num(cashflow_raw)

        rent_after_3_percent = round(rent * 1.03, 2)
        threshold = get_threshold(purchase_price)
        meets_threshold = cashflow >= threshold

        logger.debug(f"Calculated rent after 3% increase: {rent_after_3_percent}")
        logger.debug(f"Threshold for purchase price {purchase_price}: {threshold}")
        logger.debug(f"Meets threshold: {meets_threshold}")

        return jsonify({
            'message': 'Opportunity ID found!',
            'rowNumber': row_number,
            'rent': f"${rent:,.2f}",
            'purchasePrice': f"${purchase_price:,.2f}",
            'cashflow': f"${cashflow:,.2f}",
            'threshold': f"${threshold:,.2f}",
            'rentAfter3Percent': f"${rent_after_3_percent:,.2f}",
            'meetsThreshold': meets_threshold,
            # numeric values for dynamic calculations
            'rentValue': rent,
            'cashflowValue': cashflow,
            'thresholdValue': threshold,
            'purchasePriceValue': purchase_price,
            'rentAfter3PercentValue': rent_after_3_percent,
        })

    except Exception as e:
        logger.error(f"Error fetching data from Google Sheets: {e}")
        return 'Error fetching data from Google Sheets', 500


@routes.route('/calculate-cashflow', methods=['POST'])
def calculate_cashflow():
    """Calculate projected cashflow information when the rent changes.

    Expects JSON with ``currentRent``, ``currentCashflow``, ``threshold`` and
    ``newRent``. Returns the projected cashflow, difference from the threshold
    and whether the threshold is met.
    """
    data = request.get_json(force=True)
    try:
        current_rent = float(data.get('currentRent', 0))
        current_cashflow = float(data.get('currentCashflow', 0))
        threshold = float(data.get('threshold', 0))
        new_rent = float(data.get('newRent', current_rent))
    except (TypeError, ValueError):
        return 'Invalid numeric values supplied', 400

    result = calculate_cashflow_difference(
        current_rent=current_rent,
        current_cashflow=current_cashflow,
        threshold=threshold,
        new_rent=new_rent,
    )
    return jsonify(result)


@routes.route('/submit-decision', methods=['POST'])
def submit_decision():
    """Update Google Sheet with approved rent and optional lease info."""
    data = request.get_json(force=True)

    opportunity_id = data.get('opportunityId')
    approved_rent = data.get('approvedRent')
    row_number = data.get('row')
    lease_start_date = data.get('leaseStartDate')
    send_lease = bool(data.get('sendLease', False))

    if opportunity_id is None or approved_rent is None or row_number is None:
        return 'Missing required fields', 400

    try:
        approved_rent = float(approved_rent)
        row_number = int(row_number)
    except (TypeError, ValueError):
        return 'Invalid numeric values supplied', 400

    spreadsheet_id = os.environ.get('GOOGLE_SHEET_ID')
    sheet_name = os.environ.get('GOOGLE_SHEET_NAME')
    if not spreadsheet_id or not sheet_name:
        logger.error('Missing GOOGLE_SHEET_ID or GOOGLE_SHEET_NAME environment variable')
        return 'Internal config error: Missing sheet ID or name', 500

    try:
        service = get_sheets_service()
        # Only update the approved rent in column S.  Column T is reserved in the
        # sheet and should remain untouched.
        update_range = f"{sheet_name}!S{row_number}"
        body = {"values": [[approved_rent]]}
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=update_range,
            valueInputOption='USER_ENTERED',
            body=body,
        ).execute()
    except Exception as e:
        logger.error(f"Error updating sheet for Opportunity ID {opportunity_id}: {e}")
        return 'Error updating Google Sheet', 500

    try:
        # Push the approved rent to Salesforce as the monthly payment amount
        sf_fields = {
            'Monthly_Payment_Amount__c': approved_rent,
        }
        if lease_start_date:
            sf_fields['Lease_Start_Date__c'] = lease_start_date
        update_opportunity(opportunity_id, sf_fields)
    except Exception as e:
        logger.error(f"Error updating Salesforce for Opportunity ID {opportunity_id}: {e}")
        return 'Error updating Salesforce', 500

    if send_lease:
        # Placeholder for lease sending logic.  We capture the lease start date
        # from the payload but do not write it to the sheet.
        logger.info(
            "Lease send requested for Opportunity ID %s with start date %s",
            opportunity_id,
            lease_start_date,
        )

    return jsonify({'message': 'Decision submitted successfully.'})
