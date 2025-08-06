"""
Flask app to support lease renewal logic:
- Reads property and rent data from Google sheets
- Computes whether 3% rent increase meets cash flow requirements
- Updates salesforce opportunity with this updated data via JWT OAuth 
- Optionally (Not yet implemented) sends a PandaDoc lease with the new rent to the tenant
"""


import os
import time
from flask import Flask, request, jsonify, send_from_directory
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv
import requests
import jwt
from config import (
    THRESHOLD_1_LIMIT, THRESHOLD_2_LIMIT, THRESHOLD_3_LIMIT,
    THRESHOLD_1_VALUE, THRESHOLD_2_VALUE, THRESHOLD_3_VALUE, THRESHOLD_4_VALUE
) # these come from the config.py file
from typing import Optional, Dict, List, Tuple
from config import logger

# Load environment variables from .env file at runtime
load_dotenv()

app = Flask(__name__)


# -------------------------- #
#      BUSINESS LOGIC        #
# -------------------------- #

def get_threshold(purchase_price: float) -> float:
    """
    Returns the cash flow threshold based on the purchase price.
    Tiers:
    - Below 150,000: -> $225
    - 150,001 to 300,000: -> $275
    - 300,001 to 450,000: -> $400
    - Above 450,000: -> $650
    """
    if purchase_price <= THRESHOLD_1_LIMIT:
        return THRESHOLD_1_VALUE
    
    if purchase_price <= THRESHOLD_2_LIMIT:
        return THRESHOLD_2_VALUE
    
    if purchase_price <= THRESHOLD_3_LIMIT:
        return THRESHOLD_3_VALUE
    
    return THRESHOLD_4_VALUE

# -------------------------- #
#     GOOGLE SHEETS LOGIC    #
# -------------------------- #

def get_sheets_service():
    """
    Returns a Google Sheets service object using the credentials from the environment.
    """
    logger.debug('Initializing Google Sheets service...')

    creds = service_account.Credentials.from_service_account_file(
        os.getenv('GOOGLE_SHEET_CREDENTIALS_FILE'),
        scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
    )

    logger.debug('Google Sheets service initialized successfully.')

    return build('sheets', 'v4', credentials=creds)

def get_last_row(service, spreadsheet_id: str, sheet_name: str) -> int:
    """
    Returns the number of non-empty rows in column A of the given sheet.
    """
    logger.debug(f'Fetching last row from sheet: {sheet_name} in spreadsheet: {spreadsheet_id}')

    resp = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A:A"
    ).execute()
    values = resp.get('values', [])

    logger.debug(f"Last row found: {len(values)}")
    return len(values)

# -------------------------- #
#   SALESFORCE AUTH & PATCH
# -------------------------- #

def get_salesforce_access_token() -> Tuple[str, str]:
    """
    Exchanges a JWT for a salesforce access token.
    Returns (access_token, instance_url).
    """
    logger.info('Obtaining Salesforce access token...')

    private_key = os.environ['SF_JWT_KEY'].replace('\\n', '\n')
    payload = {
        'iss': os.environ['SF_CLIENT_ID'],
        'sub': os.environ['SF_USERNAME'],
        'aud': os.environ['SF_AUDIENCE'],
        'exp': int(time.time()) + 300,  # Token valid for 5 minutes
    }

    token = jwt.encode(payload, private_key, algorithm='RS256')
    params = {
        'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
        'assertion': token
    }
    response = requests.post(
        f"{os.environ['SF_LOGIN_URL']}/services/oauth2/token",
        data=params,
        headers={'Content-Type': 'application/x-www-form-urlencoded'}
    )
    response.raise_for_status()
    data = response.json()
    logger.info('Salesforce access token obtained successfully.')

    return data['access_token'], data['instance_url']

# -------------------------- #
#         ROUTES             #
# -------------------------- #

@app.route('/fetch-data')
def fetch_data():
    """
    Fetches rent, purchase price and cash flow post investor from google sheets for a given SF opportunity ID.
    Computes:
    - 3% rent increase
    - threshold requirement based on the purchase price
    - weather current cashflow meets the threshold
    - row number so we can make a quicker update later
    """
    logger.debug(f"Received request to fetch data for Opportunity ID: {opp_id}")

    opp_id: Optional[str] = request.args.get('opp_id')
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
                    row_number_map[id_val] = i + 3 # # +3 because data starts from row 3 in the sheet
        
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

