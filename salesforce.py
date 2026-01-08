import os
import time
from typing import Dict, Tuple

import jwt
import requests

from config import logger
from config import SF_JWT_KEY  



def get_salesforce_access_token() -> Tuple[str, str]:
    """Exchange a JWT for a Salesforce access token.

    Returns a tuple of ``(access_token, instance_url)``.
    """
    logger.info('Obtaining Salesforce access token...')
    payload = {
        'iss': os.environ['SF_CLIENT_ID'],
        'sub': os.environ['SF_USERNAME'],
        'aud': os.environ['SF_AUDIENCE'],
        'exp': int(time.time()) + 300,
    }
    token = jwt.encode(payload, SF_JWT_KEY, algorithm='RS256')
    params = {
        'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
        'assertion': token,
    }
    response = requests.post(
        f"{os.environ['SF_LOGIN_URL']}/services/oauth2/token",
        data=params,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
    )
    response.raise_for_status()
    data = response.json()
    logger.info('Salesforce access token obtained successfully.')
    return data['access_token'], data['instance_url']


def update_opportunity(opportunity_id: str, fields: Dict[str, object]) -> None:
    """Patch fields on a Salesforce Opportunity record.

    ``fields`` should map field API names to their desired values. Raises an
    exception if the update fails.
    """
    access_token, instance_url = get_salesforce_access_token()
    url = f"{instance_url}/services/data/v57.0/sobjects/Opportunity/{opportunity_id}"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }
    response = requests.patch(url, json=fields, headers=headers)
    response.raise_for_status()
    logger.info('Updated Salesforce Opportunity %s with fields %s', opportunity_id, fields)

def publish_lease_event(opportunity_id: str) -> None:
    """
    Publishes a Lease_Request__e platform event to trigger the Salesforce Flow.
    """
    access_token, instance_url = get_salesforce_access_token()
    
    # Note the "__e" suffix. This is required for Platform Events.
    url = f"{instance_url}/services/data/v57.0/sobjects/Lease_Request__e"
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
    }
    
    # This payload key must match the API Name of the field you just created
    payload = {
        "Opportunity_ID__c": opportunity_id
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        logger.info(f"Successfully published Lease_Request__e for Opp {opportunity_id}")
    except requests.exceptions.RequestException as e:
        # We log the error specifically so we can see if it was a 400 (Bad Request) or 403 (Permissions)
        logger.error(f"Failed to publish platform event: {e}")
        if e.response is not None:
             logger.error(f"Salesforce Response: {e.response.text}")
        raise  # Re-raise to let the caller know it failed