"""
dpres-rest-api-client default imports.
"""

from importlib.metadata import PackageNotFoundError, version

from dpres_rest_api_client.v2.client import AccessClient, DIPRequest

try:
    # pylint: disable=no-member
    __version__ = version("dpres_rest_api_client")
except PackageNotFoundError:
    __version__ = "unknown"

__all__ = ["AccessClient", "DIPRequest", "__version__"]
