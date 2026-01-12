from flask import Blueprint, request, jsonify
from typing import Optional, Dict, List
import os
from config import logger
from business import get_threshold, calculate_cashflow_difference
from sheets import get_sheets_service, get_last_row
from salesforce import update_opportunity, publish_lease_event, upload_lease_file
from fpdf import FPDF


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
    """Update Google Sheet, update Salesforce, generate PDF lease, and trigger email."""
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
        sf_fields = {
            'Monthly_Payment_Amount__c': approved_rent,
        }
        if lease_start_date:
            sf_fields['Lease_Start_Date__c'] = lease_start_date
        update_opportunity(opportunity_id, sf_fields)
    except Exception as e:
        logger.error(f"Error updating Salesforce for Opportunity ID {opportunity_id}: {e}")
        return 'Error updating Salesforce', 500

    # 3. Generate PDF and Trigger Platform Event
    if send_lease:
        logger.info("Lease send requested for Opp %s. Starting PDF generation...", opportunity_id)
        
        try:
            # --- A. Draw the PDF (The "Tinkering" Part) ---
            pdf = FPDF()
            pdf.add_page()
            
            # Simple Header
            pdf.set_font("Helvetica", style="B", size=16)
            pdf.cell(0, 10, "LEASE RENEWAL AGREEMENT", new_x="LMARGIN", new_y="NEXT", align='C')
            pdf.ln(10) # Add some space
            
            # Body Content
            pdf.set_font("Helvetica", size=12)
            
            # Define the lines of text to print
            text_lines = [
                f"Date: {lease_start_date if lease_start_date else 'TBD'}",
                f"Opportunity ID: {opportunity_id}",
                "", 
                "RE: Lease Renewal Proposal",
                "",
                f"Dear Tenant,",
                "",
                f"We are pleased to offer a renewal of your lease.",
                f"Your new monthly rent will be: ${approved_rent:,.2f}",
                "",
                "Please sign and return this document to the leasing office.",
                "",
                "Sincerely,",
                "Berry Rock Homes"
            ]
            
            # Loop through lines and print them
            for line in text_lines:
                pdf.cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")
            
            # Output to bytes (dest='S' returns the byte string in recent FPDF2 versions)
            # using pdf.output() with no arguments usually returns bytes in the latest version
            pdf_bytes = pdf.output()
            
            # --- B. Upload to Salesforce ---
            # We give it a unique name so it doesn't overwrite old ones if they click twice
            file_name = f"Lease_Renewal_{opportunity_id}.pdf"
            logger.info(f"Uploading {file_name} to Salesforce...")
            
            upload_lease_file(opportunity_id, pdf_bytes, filename=file_name)
            
            # --- C. Fire the Event ---
            # Now that the file is safely in Salesforce, we tell the Flow to send the email
            publish_lease_event(opportunity_id)
            logger.info("Platform Event published successfully.")

        except Exception as e:
            # We log the error but don't fail the request since the data was saved successfully
            logger.error(f"Error during lease generation/sending for {opportunity_id}: {e}")

    return jsonify({'message': 'Decision submitted successfully.'})