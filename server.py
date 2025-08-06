"""
Flask app to support lease renewal logic:
- Reads property and rent data from Google sheets
- Computes whether 3% rent increase meets cash flow requirements
- Updates salesforce opportunity with this updated data via JWT OAuth 
- Optionally (Not yet implemented) sends a PandaDoc lease with the new rent to the tenant
"""


import os
import time
from flask import Flask, send_from_directory
from dotenv import load_dotenv
import requests
import jwt
from typing import Optional, Dict, List, Tuple
from config import logger
from routes import routes

# Load environment variables from .env file at runtime
load_dotenv()

app = Flask(__name__)
app.register_blueprint(routes)

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
        'exp': int(time.time()) + 300,
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

if __name__ == '__main__':
    app.run(port=8080,debug=True)

