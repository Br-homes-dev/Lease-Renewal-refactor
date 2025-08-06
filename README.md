# Lease Renewal Refactor

## Overview
This project provides a small Flask application that helps evaluate rental property renewals.  It reads deal data from a Google Sheet, computes the impact of a 3% rent increase, and determines if the new cash flow meets predefined thresholds based on the purchase price.  The application can also obtain a Salesforce access token using a JWT based OAuth flow.

## Features
- Fetch rent, purchase price and cash‑flow information from a Google Sheet.
- Calculate a 3% rent increase and determine whether the cash flow meets the required threshold.
- Return JSON data that can be used by other systems.
- Example utilities for parsing numeric values and Google Sheets helpers.

## Installation
1. Create and activate a Python 3.12 virtual environment.
2. Install dependencies:
   ```bash
   pip install flask python-dotenv requests PyJWT google-api-python-client google-auth
   ```

## Configuration
The server expects several environment variables. They can be supplied via a `.env` file or your shell environment.

| Variable | Purpose |
| --- | --- |
| `GOOGLE_SHEET_ID` | ID of the Google Sheet that stores opportunity data. |
| `GOOGLE_SHEET_NAME` | Worksheet name inside the sheet. |
| `GOOGLE_SHEET_CREDENTIALS_FILE` | Path to a Google service account JSON file. |
| `SF_JWT_KEY` | Private key for Salesforce JWT authentication. |
| `SF_CLIENT_ID` | Salesforce connected app client ID. |
| `SF_USERNAME` | Username of the Salesforce user. |
| `SF_AUDIENCE` | Salesforce login URL audience. |
| `SF_LOGIN_URL` | Salesforce login base URL. |

## Running the Application
After setting the required environment variables, start the development server:

```bash
python server.py
```

The service exposes a single endpoint `GET /fetch-data?opp_id=<OPPORTUNITY_ID>` which returns the rent and threshold calculation for the given Salesforce opportunity.

## Testing
Run the test suite with:

```bash
pytest
```

Note: The current test suite may fail due to a circular import in `config.py`.

