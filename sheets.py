import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
from config import logger
from google.auth import default

def get_sheets_service():
    logger.debug('Initializing Google Sheets service...')
    creds, _ = default(scopes=['https://www.googleapis.com/auth/spreadsheets'])
    logger.debug('Google Sheets service initialized successfully.')
    return build('sheets', 'v4', credentials=creds)

def get_last_row(service, spreadsheet_id: str, sheet_name: str) -> int:
    logger.debug(f'Fetching last row from sheet: {sheet_name} in spreadsheet: {spreadsheet_id}')
    resp = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A:A"
    ).execute()
    values = resp.get('values', [])
    logger.debug(f"Last row found: {len(values)}")
    return len(values)
