"""
dpres-rest-api-client default imports.
"""

from dpres_rest_api_client.v2.client import AccessClient, DIPRequest
from dpres_rest_api_client.version import __version__

__all__ = ["AccessClient", "DIPRequest", "__version__"]
