"""
dpres-rest-api-client default imports
"""

from importlib.metadata import PackageNotFoundError, version

# flake8: noqa
from .v2.client import AccessClient, DIPRequest

try:
    # pylint: disable=no-member
    __version__ = version("dpres_rest_api_client")
except PackageNotFoundError:
    __version__ = "unknown"
