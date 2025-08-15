import os
import logging

THRESHOLD_1_LIMIT = 150000
THRESHOLD_2_LIMIT = 300000
THRESHOLD_3_LIMIT = 450000

THRESHOLD_1_VALUE = 225.0
THRESHOLD_2_VALUE = 275.0
THRESHOLD_3_VALUE = 400.0
THRESHOLD_4_VALUE = 650.0

ENABLE_LEASE_GENERATION = False

LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()

logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%y-%m-%d %H:%M:%S'
)

logger = logging.getLogger("lease-renewal")

SF_JWT_KEY_PATH = os.getenv("SF_JWT_KEY_PATH", "/var/secrets/SF_JWT_KEY")

with open(SF_JWT_KEY_PATH, 'r') as key_file:
    SF_JWT_KEY = key_file.read()
