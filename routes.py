from flask import Blueprint, request, jsonify
from typing import Optional, Dict, List
import os
from config import logger
from business import get_threshold
from sheets import get_sheets_service, get_last_row

routes = Blueprint('routes', __name__)

@routes.route('/fetch-data')
def fetch_data():
    """
    Fetches rent, purchase price and cash flow post investor from google sheets for a given SF opportunity ID.
    Computes:
    - 3% rent increase
    - threshold requirement based on the purchase price
    - weather current cashflow meets the threshold
    - row number so we can make a quicker update later
    """
    opp_id: Optional[str] = request.args.get('opp_id')
    logger.debug(f"Received request to fetch data for Opportunity ID: {opp_id}")
    if not opp_id:
        return 'Please provide an Opportunity ID as a query parameter: ?oppId=...', 400
    
    spreadsheet_id = os.environ.get('GOOGLE_SHEET_ID')
    sheet_name = os.environ.get('GOOGLE_SHEET_NAME')
    logger.debug(f"Spreadsheet ID: {spreadsheet_id}, Sheet Name: {sheet_name}")

    try:
        service = get_sheets_service()
        last_row = get_last_row(service, spreadsheet_id, sheet_name)

        # Data starts in row 3 due to header
        range = f"{sheet_name}!A3:BV{last_row}"
        resp = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range
        ).execute()

        rows = resp.get('values', [])

        id_to_row : Dict[str,List[str]] = {}
        row_number_map: Dict[str,int] = {}

        for i, row in enumerate(rows):
            if len(row) > 73:
                id_val = row[73].strip()
                if id_val:
                    id_to_row[id_val] = row
                    row_number_map[id_val] = i + 3 # +3 because data starts from row 3 in the sheet
        
        logger.debug(f"Fetched {len(rows)} rows from Google Sheets.")
        
        if opp_id not in id_to_row:
            logger.debug(f"No data found for Opportunity ID: {opp_id}")
            return f"No data found for Opportunity ID: {opp_id}", 404
        
        found_row = id_to_row[opp_id]
        row_number = row_number_map[opp_id]

        # Sheet columns mapping
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
            'rent': rent,
            'purchasePrice': purchase_price,
            'cashflow': cashflow,
            'threshold': threshold,
            'rentAfter3Percent': rent_after_3_percent,
            'meetsThreshold': meets_threshold,
        })
    
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return 'Error fetching data from Google Sheets', 500
