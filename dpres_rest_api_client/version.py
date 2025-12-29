"""Define the version of DPRES REST API Client."""

try:
    from dpres_rest_api_client._version import version as __version__
except ImportError:
    # Package not installed
    __version__ = "unknown"
