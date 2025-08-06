import logging

THRESHOLD_1_LIMIT = 150000
THRESHOLD_2_LIMIT = 300000
THRESHOLD_3_LIMIT = 450000

THRESHOLD_1_VALUE = 225.0 # <= 150,000
THRESHOLD_2_VALUE = 275.0 # 150,001 - 300,000
THRESHOLD_3_VALUE = 400.0 # 300,001 - 450,000
THRESHOLD_4_VALUE = 650.0 # > 450,000

ENABLE_LEASE_GENERATION = False  # Set to True to enable lease generation

# set logging level from env or default to INFO
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()

logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%y-%m-%d %H:%M:%S'
)

logger = logging.getLogger("lease-renewal")