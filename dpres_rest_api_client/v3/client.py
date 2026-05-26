"""
Client module to utilize National Digital Preservation Services REST API 3.0.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, TypedDict, TypeVar

from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError
from tusclient import client
from tusclient.storage import filestorage

from dpres_rest_api_client.base import BaseClient

if TYPE_CHECKING:
    from tusclient.uploader import Uploader


Result = TypeVar("Result")


@dataclass
class SearchResultV3(Generic[Result]):
    """
    Container for a set of search results
    """
    results: list[Result]
    has_next_page: bool
    page: int
    limit: int

    @classmethod
    def from_data(cls, data: dict, page: int, limit: int) -> SearchResultV3:
        return cls(
            results=data["results"],
            has_next_page=bool(data["links"].get("next")),
            page=page,
            limit=limit
        )


class AIPResult(TypedDict):
    """
    Individual result entry returned by search and /v3/<contract>/search
    """
    aip_id: str
    content_id: str | None
    createdate: str
    lastmoddate: str | None
    location: str
    match: dict | None


class TransferResult(TypedDict):
    """
    Individual result entry returned by list_transfers and
    /v3/<contract>/transfers
    """
    transfer_id: str
    filename: str
    status: str
    transfer: str | None
    actions: dict
    sip: str
    timestamp: str


class DIPResult(TypedDict):
    """
    Individual result entry returned by list_dips and
    /v3/<contract>/disseminated
    """
    dip_id: str
    complete: bool
    disseminated: str
    actions: dict
    timestamp: str


class DipInfoResult(TypedDict):
    """
    Result returned from get_dip_info and /v3/<contract>/disseminated/<dip-id>
    """
    dip_id: str
    complete: bool
    actions: dict
    dip: dict
    timestamp: str


class StatisticsResult(TypedDict):
    """Individual result returned by `/v3/<contract>/statistics/overview`"""

    capacity: _CapacityStats
    key_figures: _KeyFiguresStats


class _CapacityStats(TypedDict):
    used: int
    available: int
    total: int


class _KeyFiguresStats(TypedDict):
    sips_accepted: int
    objects_preserved: int


class RestClient(BaseClient):
    """
    Client for using the Digital Preservation Service REST API.
    """

    def __init__(self, config=None):
        """
        Create the RestClient instance.
        """
        super().__init__(api="3.0", config=config)
        # TUS endpoint is a bit special in DPS that contract ID is not provided
        # in the URL.
        self._tus_endpoint = f"{self.host}/api/{self.api_version}/transfers"
        self._tus_client = None

    def _create_tus_client(self):
        """Creates and returns a tus client instance tailored for
        Digital Preservation Service.

        :return: TusClient object.
        """
        tus_client = client.TusClient(self.tus_endpoint)
        auth = HTTPBasicAuth(
            username=self.session.auth[0], password=self.session.auth[1]
        )
        tus_client.headers["User-Agent"] = self.session.headers["User-Agent"]
        tus_client = auth(tus_client)
        return tus_client

    @property
    def tus_client(self):
        """Returns TusClient object.

        :return: TusClient object.
        """
        if self._tus_client is None:
            self._tus_client = self._create_tus_client()
        return self._tus_client

    @property
    def tus_endpoint(self):
        """Returns TUS endpoint of Digital Preservation Service.

        :return: TUS endpoint in string.
        """
        return self._tus_endpoint

    def create_uploader(
        self,
        file_path: str,
        chunk_size: int | None = None,
        store_url: bool = False,
        cache_file: str = "dpres_rest_api_client_tus_storage",
    ) -> Uploader:
        """Create TUS Uploader object tailored for Digital Preservation
        Service.

        :param file_path: String path to the file that will be uploaded.
        :param chunk_size: Integer value on how big of a bytes each chunk
            should be when uploading. None for no limit.
        :param store_url: Boolean whether to cache the URLs for given file
            to later try and resume. Defaulted to False.
        :param cache_file: Which file to use to cache TUS storage for
            resumable usage. This is only utilized when store_url is True.
        :return: TUS Uploader-instance.
        """
        kwargs: dict[str, Any] = {
            "metadata": {
                "contract_id": self.contract_id,
                "filename": os.path.basename(file_path),
            }
        }
        if chunk_size:
            kwargs["chunk_size"] = chunk_size
        if self.session.verify is False:
            kwargs["verify_tls_cert"] = False

        if store_url:
            storage = filestorage.FileStorage(cache_file)
            kwargs["store_url"] = True
            kwargs["url_storage"] = storage

        uploader = self.tus_client.uploader(file_path=file_path, **kwargs)
        return uploader

    def get_transfer(self, transfer_id):
        """Get transfer information from Digital Preservation Service.

        :param transfer_id: Transfer ID to fetch the information for.
        :return: JSON data from successful response.
        :raises HTTPError: When response code is within 400 - 599 range.
        """
        url = f"{self.base_url}/transfers/{transfer_id}"
        response = self.session.get(url)
        return response.json()["data"]

    def get_validation_report(self, transfer_id, report_type="xml"):
        """Get validation report for given transfer.

        :param transfer_id: Transfer ID to fetch the report for.
        :param report_type: Report type to download, either "xml" or "html"
            (default: xml).
        :return: Content data in bytes from successful response.
        :raises HTTPError: When response code is within 400 - 599 range.
        """
        url = f"{self.base_url}/transfers/{transfer_id}/report"
        params = {"type": report_type}
        response = self.session.get(url, params=params)
        return response.content

    def delete_transfer(self, transfer_id):
        """Delete the given transfer information.

        This will make it so that future call to get transfer
        information or report is no longer possible.

        :param transfer_id: Transfer ID to delete.
        :return: True on success, otherwise False.
        """
        url = f"{self.base_url}/transfers/{transfer_id}"
        try:
            self.session.delete(url)
            return True
        except HTTPError:
            return False

    def list_transfers(
        self,
        status=None,
        page=1,
        limit=20
    ) -> SearchResultV3[TransferResult]:
        """
        Get list of recent transfers from Digital Preservation Service.

        :param status: Filter the result down to given status in string.
        :param page: Which page number to view in integer.
        :param limit: Limit to how many results in integer.
        :return: JSON data from successful response.
        :raises HTTPError: When response code is within 400 - 599 range.
        """
        url = f"{self.base_url}/transfers"
        params = {"page": page, "limit": limit}
        if status:
            params["status"] = status
        response = self.session.get(url, params=params)
        data = response.json()["data"]

        return SearchResultV3[TransferResult].from_data(
            data=data, page=page, limit=limit
        )

    def search(
        self,
        page: int = 1,
        limit: int = 1000,
        query: str | None = None
    ) -> SearchResultV3[AIPResult]:
        """
        Perform a search for packages and return a SearchResult

        :param page: Search result page.
                     Defaults to 1 (i.e. the first page).
        :param limit: Maximum amount of search results per page
        :param query: Search query based on Solr's dialect of the
                      Lucene query syntax.
        """
        params = {"page": page, "limit": limit}

        if query:
            params["q"] = query

        response = self.session.get(f"{self.base_url}/search", params=params)
        data = response.json()["data"]

        return SearchResultV3[AIPResult].from_data(
            data=data, page=page, limit=limit
        )

    def list_dips(
        self,
        complete: bool | None = None,
        page: int = 1,
        limit: int = 20
    ) -> SearchResultV3[DIPResult]:
        """
        List of completed DIPs in Digital Preservation Service.
        Incompleted DIPs are listed using completed=False parameter.

        :param bool complete: True lists only the completed DIPs.
        False lists DIPs in progress. Default value None returns
        all DIPs regardless of the completion status.
        :param int page: Which response page to view as an integer.
        :param int limit: Maximum number of DIPs as an integer.
        :raises HTTPError: When response code is wihin 400 - 599 range.
        """
        url = f"{self.base_url}/disseminated"
        params = {"page": page, "limit": limit}
        if complete is not None:
            params['complete'] = complete

        response = self.session.get(url, params=params)
        data = response.json()["data"]

        return SearchResultV3[DIPResult].from_data(
            data=data, page=page, limit=limit
        )

    def get_statistics(self) -> StatisticsResult:
        """Get the statistics overview for a contract"""
        url = f"{self.base_url}/statistics/overview"
        response = self.session.get(url)
        data = response.json()["data"]
        return StatisticsResult(**data)

    def get_dip_info(self, dip_id: str) -> DipInfoResult:
        url = f"{self.base_url}/disseminated/{dip_id}"
        response = self.session.get(url).json()["data"]
        return response
