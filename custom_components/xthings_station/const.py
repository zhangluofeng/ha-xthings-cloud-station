"""Constants for Xthings Cloud integration."""

import logging

DOMAIN = "xthings_station"
LOGGER = logging.getLogger(__package__)

CONF_REFRESH_TOKEN = "refresh_token"
CONF_INSTANCE_ID = "instance_id"
CONF_REMOTE_ACCESS = "remote_access"

# FRP artifact distribution base URL
FRP_S3_BASE_URL = "https://xthings-deploy-package.s3.us-west-2.amazonaws.com/Frp"
