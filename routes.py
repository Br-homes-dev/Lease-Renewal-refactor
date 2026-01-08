from flask import Blueprint, request, jsonify
from typing import Optional, Dict, List
import os
from config import logger
from business import get_threshold, calculate_cashflow_difference
from sheets import get_sheets_service, get_last_row
from salesforce import update_opportunity, publish_lease_event

routes = Blueprint('routes', __name__)

@routes.route('/fetch-data')
def fetch_data():
    """
    Fetches rent, purchase price and cash flow from Google Sheets for a given SF opportunity ID.
    Uses fully dynamic column headers to prevent errors when columns are moved or added.
    """
    # --- CONFIGURATION: EXACT HEADER NAMES FROM ROW 2 ---
    COLUMN_NAMES = {
        'opp_id': 'Opportunity ID',
        'rent': 'Rent Income',
        'price': 'Original Purchase Price/ Value',
        'cashflow': 'Post Investor Monthly Cashflow'
    }
    # ----------------------------------------------------

    opp_id: Optional[str] = request.args.get('opp_id')
    logger.debug(f"Received request to fetch data for Opportunity ID: {opp_id}")
    if not opp_id:
        return 'Please provide an Opportunity ID as a query parameter: ?opp_id=...', 400

    spreadsheet_id = os.environ.get('GOOGLE_SHEET_ID')
    sheet_name = os.environ.get('GOOGLE_SHEET_NAME')

    if not spreadsheet_id or not sheet_name:
        logger.error("Missing GOOGLE_SHEET_ID or GOOGLE_SHEET_NAME environment variable")
        return 'Internal config error: Missing sheet ID or name', 500

    try:
        service = get_sheets_service()
        last_row = get_last_row(service, spreadsheet_id, sheet_name)

        # Start from A2 to capture headers (Row 2) and all data up to column ZZ
        range = f"{sheet_name}!A2:ZZ{last_row}"
        resp = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range
        ).execute()

        all_rows = resp.get('values', [])
        if not all_rows:
            return "No data found in sheet", 404

        # Row 2 contains headers, Row 3+ contains data
        headers = all_rows[0]
        data_rows = all_rows[1:]

        # Create a map of "Column Name" -> Index
        # We strip() whitespace to handle accidental spaces like " Rent Income "
        header_map = {name.strip(): i for i, name in enumerate(headers)}
        
        # Verify all required columns exist
        column_indices = {}
        missing_columns = []
        
        for key, sheet_header_name in COLUMN_NAMES.items():
            if sheet_header_name in header_map:
                column_indices[key] = header_map[sheet_header_name]
            else:
                missing_columns.append(sheet_header_name)

        if missing_columns:
            error_msg = f"Configuration Error: The following columns were not found in Row 2: {', '.join(missing_columns)}"
            logger.error(error_msg)
            # Log the headers we DID find to help debugging
            logger.error(f"Headers actually found in sheet: {list(header_map.keys())}")
            return error_msg, 500

        # Helper to get value safely from a row using our dynamic index
        def get_col_val(row_data, col_key):
            idx = column_indices[col_key]
            if len(row_data) > idx:
                return row_data[idx]
            return ''

        # Search for the Opportunity ID
        id_to_row = {}
        row_number_map = {}
        opp_id_idx = column_indices['opp_id']

        for i, row in enumerate(data_rows):
            if len(row) > opp_id_idx:
                raw_id = row[opp_id_idx]
                if raw_id:
                    # Normalize ID for comparison
                    id_val = ''.join(raw_id.split()).lower()
                    id_to_row[id_val] = row
                    # i=0 is Row 3, so Row Number = i + 3
                    row_number_map[id_val] = i + 3

        normalized_request_id = ''.join(opp_id.split()).lower()
        
        if normalized_request_id not in id_to_row:
            logger.debug(f"No data found for Opportunity ID: {opp_id}")
            return f"No data found for Opportunity ID: {opp_id}", 404

        found_row = id_to_row[normalized_request_id]
        row_number = row_number_map[normalized_request_id]

        # Fetch data using the dynamic indices
        rent_raw = get_col_val(found_row, 'rent')
        purchase_price_raw = get_col_val(found_row, 'price')
        cashflow_raw = get_col_val(found_row, 'cashflow')

        logger.debug(f"Parsed values - Rent: {rent_raw}, Price: {purchase_price_raw}, Cashflow: {cashflow_raw}")

        def parse_num(value: str) -> float:
            return float(''.join(ch for ch in value if ch in '0123456789.-')) if value else 0.0

        rent = parse_num(rent_raw)
        purchase_price = parse_num(purchase_price_raw)
        cashflow = parse_num(cashflow_raw)

        rent_after_3_percent = round(rent * 1.03, 2)
        threshold = get_threshold(purchase_price)
        meets_threshold = cashflow >= threshold

        return jsonify({
            'message': 'Opportunity ID found!',
            'rowNumber': row_number,
            'rent': f"${rent:,.2f}",
            'purchasePrice': f"${purchase_price:,.2f}",
            'cashflow': f"${cashflow:,.2f}",
            'threshold': f"${threshold:,.2f}",
            'rentAfter3Percent': f"${rent_after_3_percent:,.2f}",
            'meetsThreshold': meets_threshold,
            'rentValue': rent,
            'cashflowValue': cashflow,
            'thresholdValue': threshold,
            'purchasePriceValue': purchase_price,
            'rentAfter3PercentValue': rent_after_3_percent,
        })

    except Exception as e:
        logger.error(f"Error fetching data from Google Sheets: {e}")
        return f"Error fetching data: {str(e)}", 500


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

    # 1. Update Google Sheets
    try:
        service = get_sheets_service()
        # Only update the approved rent in column S. Column T is reserved.
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

    # 2. Update Salesforce Opportunity Record
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

    # 3. Trigger Platform Event (The New Part)
    if send_lease:
        logger.info(
            "Lease send requested for Opportunity ID %s. Publishing Platform Event...",
            opportunity_id,
        )
        try:
            #Triggers the flow via the Platform Event
            publish_lease_event(opportunity_id)
        except Exception as e:
            # Log error but do not fail the request since data was saved successfully
            logger.error(f"Error publishing Salesforce Event for {opportunity_id}: {e}")

    return jsonify({'message': 'Decision submitted successfully.'})