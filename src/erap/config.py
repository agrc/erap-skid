"""
config.py: Configuration values. Secrets to be handled with Secrets Manager
"""

import logging
import socket
from pathlib import Path

import numpy as np

PROJECT_ID = 'ut-dts-agrc-erap-dev'
# SECRET_NAMES = [
#     'AGOL_USER',
#     'AGOL_PASSWORD',
#     'SFTP_HOST',
#     'SFTP_USERNAME',
#     'SFTP_PASSWORD',
#     'SFTP_FOLDER',
#     # 'SENDGRID_API_KEY',  #: requested before the rest in separate call
# ]
AGOL_ORG = 'https://utah.maps.arcgis.com'
# AGOL_USER =
# AGOL_PASSWORD =
SENDGRID_SETTINGS = {  #: Settings for SendGridHandler
    # 'api_key':
    'from_address': 'noreply@utah.gov',
    'to_addresses': 'jdadams@utah.gov',
    'prefix': f'ERAP on {socket.gethostname()}: ',
}
LOG_LEVEL = logging.DEBUG

# SFTP_HOST =
# SFTP_USERNAME =
# SFTP_PASSWORD =
# SFTP_FOLDER =
KNOWNHOSTS = f'{Path(__file__).parent.parent.parent}\\known_hosts'
ERAP_FILE_NAME = 'ERAP_PAYMENTS.csv'
ERAP_KEY_COLUMN = 'zip5'
ERAP_CLASSIFICATION_COLUMN = 'Amount'

ERAP_FEATURE_SERVICE_URL = (
    'https://services1.arcgis.com/99lidPhWCzftIe9K/arcgis/rest/services/ERAP_By_Zipcode/FeatureServer/0'
)
ERAP_FEATURE_LAYER_ITEMID = '32f9c17b1ed04157a8a9a0a635f36c64'
ERAP_WEBMAP_ITEMID = 'c14586a1117e4fd1a0865ffa9e3a9a37'
ERAP_LAYER_NAME = 'Aggregate Paid Rental Assistance Applications'

ERAP_LOG_NAME = 'log'
ERAP_DATA_TYPES = {
    'zip5': str,
    'Count_': str,
    'Amount': np.float64,
    'Updated': str,
}

STORAGE_BUCKET = 'ut-dts-agrc-erap-dev-data'
