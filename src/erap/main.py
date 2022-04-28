#!/usr/bin/env python
# * coding: utf8 *
"""
Updates the DWS ERAP layer based on their weekly
"""

import json
import logging
import sys
from datetime import datetime
from os import environ
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

import arcgis
from google.cloud import storage
from palletjack import ColorRampReclassifier, FeatureServiceInlineUpdater, SFTPLoader
from supervisor.message_handlers import SendGridHandler
from supervisor.models import MessageDetails, Supervisor

#: This makes it work when calling with just `python <file>`/installing via pip and in the gcf framework, where
#: the relative imports fail because of how it's calling the function.
try:
    from . import config, version
except ImportError:
    import config
    import version

STORAGE_BUCKET = environ.get('STORAGE_BUCKET')


def _initialize(log_path, sendgrid_api_key):

    erap_logger = logging.getLogger('erap')
    erap_logger.setLevel(config.LOG_LEVEL)
    palletjack_logger = logging.getLogger('palletjack')
    palletjack_logger.setLevel(config.LOG_LEVEL)

    cli_handler = logging.StreamHandler(sys.stdout)
    cli_handler.setLevel(config.LOG_LEVEL)
    formatter = logging.Formatter(
        fmt='%(levelname)-7s %(asctime)s %(name)15s:%(lineno)5s %(message)s', datefmt='%Y-%m-%d %H:%M:%S'
    )
    cli_handler.setFormatter(formatter)

    log_handler = logging.FileHandler(log_path, mode='w')
    log_handler.setLevel(config.LOG_LEVEL)
    log_handler.setFormatter(formatter)

    erap_logger.addHandler(cli_handler)
    erap_logger.addHandler(log_handler)
    palletjack_logger.addHandler(cli_handler)
    palletjack_logger.addHandler(log_handler)

    #: Log any warnings at logging.WARNING
    #: Put after everything else to prevent creating a duplicate, default formatter
    #: (all log messages were duplicated if put at beginning)
    logging.captureWarnings(True)

    erap_logger.debug('Creating Supervisor object')
    erap_supervisor = Supervisor(handle_errors=False)
    sendgrid_settings = config.SENDGRID_SETTINGS
    sendgrid_settings['api_key'] = sendgrid_api_key
    erap_supervisor.add_message_handler(
        SendGridHandler(sendgrid_settings=sendgrid_settings, client_name='erap', client_version=version.__version__)
    )

    return erap_supervisor


def _get_secrets():
    secret_folder = Path('/secrets')

    if secret_folder.exists():
        return json.loads(Path('/secrets/app/secrets.json').read_text(encoding='utf-8'))

    secret_folder = (Path(__file__).parent / 'secrets')
    if secret_folder.exists():
        return json.loads((secret_folder / 'secrets.json').read_text(encoding='utf-8'))

    raise FileNotFoundError('Secrets folder not found; secrets not loaded.')


def process():
    """Primary ERAP skid
    """

    start = datetime.now()

    secrets = SimpleNamespace(**_get_secrets())

    tempdir = TemporaryDirectory()
    tempdir_path = Path(tempdir.name)
    log_name = f'{config.ERAP_LOG_NAME}_{start.strftime("%Y%m%d-%H%M%S")}.txt'
    log_path = tempdir_path / log_name

    erap_supervisor = _initialize(log_path, secrets.SENDGRID_API_KEY)

    module_logger = logging.getLogger('erap')

    module_logger.debug('Logging into `%s` as `%s`', config.AGOL_ORG, secrets.AGOL_USER)
    gis = arcgis.gis.GIS(config.AGOL_ORG, secrets.AGOL_USER, secrets.AGOL_PASSWORD)
    erap_webmap_item = gis.content.get(config.ERAP_WEBMAP_ITEMID)  # pylint: disable=no-member

    #: Load the latest data from FTP
    module_logger.info('Getting data from FTP')
    knownhosts = Path('/secrets/ftp/known_hosts/')
    if not knownhosts.exists():
        knownhosts = config.KNOWNHOSTS
    erap_loader = SFTPLoader(secrets.SFTP_HOST, secrets.SFTP_USERNAME, secrets.SFTP_PASSWORD, knownhosts, tempdir_path)
    files_downloaded = erap_loader.download_sftp_folder_contents(sftp_folder=secrets.SFTP_FOLDER)
    dataframe = erap_loader.read_csv_into_dataframe(config.ERAP_FILE_NAME, config.ERAP_DATA_TYPES)

    #: Save the source file to Cloud storage for future reference; bucket should have an age-based retention policy
    module_logger.info('Saving data file to Cloud Storage')
    file_base_name = str(config.ERAP_FILE_NAME).split('.', maxsplit=1)[0]
    blob_name = f'{file_base_name}_{start.strftime("%Y%m%d-%H%M%S")}.csv'
    file_blob = storage.Client() \
                       .bucket(STORAGE_BUCKET) \
                       .blob(blob_name)
    file_blob.upload_from_filename(tempdir_path / config.ERAP_FILE_NAME)

    #: Update the AGOL data
    module_logger.info('Updating data in AGOL')
    erap_updater = FeatureServiceInlineUpdater(gis, dataframe, config.ERAP_KEY_COLUMN)
    rows_updated = erap_updater.update_existing_features_in_hosted_feature_layer(
        config.ERAP_FEATURE_LAYER_ITEMID, list(config.ERAP_DATA_TYPES.keys())
    )

    #: Reclassify the break values on the webmap's color ramp
    module_logger.info('Reclassifying the map')
    erap_reclassifier = ColorRampReclassifier(erap_webmap_item, gis)
    success = erap_reclassifier.update_color_ramp_values(config.ERAP_LAYER_NAME, config.ERAP_CLASSIFICATION_COLUMN)

    reclassifier_result = 'Success'
    if not success:
        reclassifier_result = 'Failure'

    end = datetime.now()

    summary_message = MessageDetails()
    summary_message.subject = 'ERAP Update Summary'
    summary_rows = [
        f'ERAP update {start.strftime("%Y-%m-%d")}',
        '=' * 20,
        '',
        f'Start time: {start.strftime("%H:%M:%S")}',
        f'End time: {end.strftime("%H:%M:%S")}',
        f'Duration: {str(end-start)}',
        f'{files_downloaded} files downloaded from SFTP',
        f'{rows_updated} rows updated in Feature Service',
        f'Reclassifier webmap update operation: {reclassifier_result}',
    ]
    summary_message.message = '\n'.join(summary_rows)
    summary_message.attachments = tempdir_path / log_name

    erap_supervisor.notify(summary_message)

    module_logger.info('Saving log to Cloud Storage')
    log_blob = storage.Client() \
                      .bucket(STORAGE_BUCKET) \
                      .blob(log_name)
    log_blob.upload_from_filename(tempdir_path / log_name)

    #: Try to clean up the tempdir (we don't use a context manager); log any errors as a heads up
    #: This dir shouldn't persist between cloud function calls, but in case it does, we try to clean it up
    try:
        tempdir.cleanup()
    except Exception as error:
        module_logger.error(error)


def main(event, context):  # pylint: disable=unused-argument
    """Entry point for Google Cloud Function triggered by pub/sub event

    Args:
         event (dict):  The dictionary with data specific to this type of
                        event. The `@type` field maps to
                         `type.googleapis.com/google.pubsub.v1.PubsubMessage`.
                        The `data` field maps to the PubsubMessage data
                        in a base64-encoded string. The `attributes` field maps
                        to the PubsubMessage attributes if any is present.
         context (google.cloud.functions.Context): Metadata of triggering event
                        including `event_id` which maps to the PubsubMessage
                        messageId, `timestamp` which maps to the PubsubMessage
                        publishTime, `event_type` which maps to
                        `google.pubsub.topic.publish`, and `resource` which is
                        a dictionary that describes the service API endpoint
                        pubsub.googleapis.com, the triggering topic's name, and
                        the triggering event type
                        `type.googleapis.com/google.pubsub.v1.PubsubMessage`.
    Returns:
        None. The output is written to Cloud Logging.
    """

    process()


if __name__ == '__main__':
    #: the code that executes if you run the file or module directly
    process()
