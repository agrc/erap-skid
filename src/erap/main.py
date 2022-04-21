#!/usr/bin/env python
# * coding: utf8 *
"""
Updates the DWS ERAP layer based on their weekly
"""

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

import arcgis
from palletjack import ColorRampReclassifier, FeatureServiceInlineUpdater, SFTPLoader
from supervisor.message_handlers import SendGridHandler
from supervisor.models import MessageDetails, Supervisor

#: This makes it work when calling with just python <file>/installing via pip and in the gcf framework, where
#: the relative imports fail because of how it's calling the function.
try:
    from . import config, rotating
except ImportError:
    import config
    import rotating


def _initialize():

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

    log_handler = RotatingFileHandler(config.ERAP_LOG_PATH, backupCount=config.ROTATE_COUNT)
    log_handler.doRollover()  #: Rotate the log on each run
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
    erap_supervisor = Supervisor(logger=erap_logger, log_path=config.ERAP_LOG_PATH)
    erap_supervisor.add_message_handler(
        SendGridHandler(sendgrid_settings=config.SENDGRID_SETTINGS, project_name='erap')
    )

    return erap_supervisor


def process():
    """Primary ERAP skid
    """

    start = datetime.now()

    erap_supervisor = _initialize()

    module_logger = logging.getLogger(__name__)

    module_logger.debug('Logging into `%s` as `%s`', config.AGOL_ORG, config.AGOL_USER)
    gis = arcgis.gis.GIS(config.AGOL_ORG, config.AGOL_USER, config.AGOL_PASSWORD)
    erap_webmap_item = gis.content.get(config.ERAP_WEBMAP_ITEMID)  # pylint: disable=no-member
    rotator = rotating.FolderRotator(config.ERAP_BASE_DIR)
    erap_download_dir = rotator.get_rotated_directory(max_folder_count=config.ROTATE_COUNT)

    #: Load the latest data from FTP
    module_logger.info('Getting data from FTP')
    erap_loader = SFTPLoader(
        config.SFTP_HOST, config.SFTP_USERNAME, config.SFTP_PASSWORD, config.KNOWNHOSTS, erap_download_dir
    )
    files_downloaded = erap_loader.download_sftp_folder_contents(sftp_folder=config.SFTP_FOLDER)
    dataframe = erap_loader.read_csv_into_dataframe(config.ERAP_FILE_NAME, config.ERAP_DATA_TYPES)

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
    summary_message.attachments = config.ERAP_LOG_PATH

    erap_supervisor.notify(summary_message)


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
    # main()
    print()
