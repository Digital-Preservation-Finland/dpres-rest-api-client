"""Define the version of DPRES REST API Client."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("dpres_rest_api_client")
except PackageNotFoundError:
    __version__ = "unknown"
