"""
Client module to utilize National Digital Preservation Services REST API 3.0.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generic, TypeVar
from collections.abc import Iterator

from requests import Response, Request, PreparedRequest
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
    def from_data(
        cls,
        data: dict,
        page: int,
        limit: int,
        entry_type: type,
    ) -> SearchResultV3:

        results_ = [
            cls._cast_results(entry, entry_type) for entry in data["results"]
        ]

        return cls(
            results=results_,
            has_next_page=bool(data["links"].get("next")),
            page=page,
            limit=limit
        )

    @staticmethod
    def _cast_results(
        entry: dict, entry_type: type
    ) -> (
        None
        | AIPResult
        | TransferResult
        | DIPResult
        | AIPFileListEntry
        | AIPDivListEntry
    ):
        if entry_type == AIPResult:
            return AIPResult(
                AIPID(entry["aip_id"]),
                entry.get("content_id"),
                entry["createdate"],
                entry.get("lastmoddate"),
                entry["location"],
                entry.get("match"),
            )
        elif entry_type == TransferResult:
            return TransferResult(
                TransferID(entry["transfer_id"]),
                entry["filename"],
                entry["status"],
                entry.get("transfer"),
                entry["actions"],
                entry["sip"],
                entry["timestamp"],
            )
        elif entry_type == DIPResult:
            return DIPResult(
                DIPID(entry["dip_id"]),
                entry["complete"],
                entry["disseminated"],
                entry["actions"],
                entry["timestamp"],
            )
        elif entry_type == AIPFileListEntry:
            return AIPFileListEntry(
                entry["filepath"],
                entry["file_id"],
            )
        elif entry_type == AIPDivListEntry:
            return AIPDivListEntry(
                entry["div_id"],
                DivAttributes(
                    entry["attributes"].get("label"),
                    entry["attributes"].get("type"),
                    entry["attributes"].get("order"),
                    entry["attributes"].get("orderlabel"),
                ),
            )
        return None


@dataclass
class AIPResult:
    """
    Individual result entry returned by :meth:`RestClient.search` and
    /v3/<contract>/search
    """

    aip_id: AIPID
    content_id: str | None
    createdate: str
    lastmoddate: str | None
    location: str
    match: dict | None


@dataclass
class TransferResult:
    """
    Individual result entry returned by :meth:`RestClient.list_transfers` and
    /v3/<contract>/transfers
    """

    transfer_id: TransferID
    filename: str
    status: str
    transfer: str | None
    actions: dict
    sip: str
    timestamp: str


@dataclass
class DIPResult:
    """
    Individual result entry returned by :meth:`RestClient.list_dips` and
    /v3/<contract>/disseminated
    """

    dip_id: DIPID
    complete: bool
    disseminated: str
    actions: dict
    timestamp: str


@dataclass
class AIPFileListEntry:
    """
    Individual result entry returned by :meth:`RestClient.list_aip_files` and
    /v3/<contract>/preserved/<aip>/files
    """
    filepath: str
    file_id: str


@dataclass
class DivAttributes:
    """
    A helper class that contains div specific information.
    """
    label: str | None
    type: str | None
    order: str | None
    orderlabel: str | None


@dataclass
class AIPDivListEntry:
    """
    Individual result entry returned by :meth:`RestClient.list_aip_divs` and
    /v3/<contract>/preserved/<aip>/divs
    """
    div_id: str
    attributes: DivAttributes


@dataclass
class DIPInfoResult:
    """
    Result returned from :meth:`RestClient.get_dip_info` and
    /v3/<contract>/disseminated/<dip-id>
    """

    dip_id: DIPID
    complete: bool
    actions: dict
    dip: dict
    timestamp: str


@dataclass
class StatisticsResult:
    """
    Result returned by :meth:`RestClient.get_statistics` and
    /v3/<contract>/statistics/overview
    """

    capacity: _CapacityStats
    key_figures: _KeyFiguresStats


@dataclass
class _CapacityStats:
    used: int
    available: int
    total: int


@dataclass
class _KeyFiguresStats:
    sips_accepted: int
    objects_preserved: int


class DIPDownloader:
    """
    A utility class for helping to download DIP files.
    """

    def __init__(self, response: Response):
        """
        :param response: *Streaming* response, from which content is read.
        """
        self._response = response

        content_disposition = response.headers["Content-Disposition"]
        prefix = "attachment; filename="
        self.suggested_filename = \
            content_disposition[len(prefix):].strip('"\'')

    @property
    def download_iter(self) -> Iterator[bytes]:
        """
        Iterator for reading the file
        """
        yield from self._response.iter_content(chunk_size=1024 * 1024)

    def save(self, path: os.PathLike | str) -> Path:
        """
        Saves the file to disk.
        :param path: A path to specify where to save the file.
        :return: The path where the file is saved.
        """

        resolved_path = Path(path)

        with open(resolved_path, "wb", buffering=1024 * 1024) as file_:
            for chunk in self.download_iter:
                file_.write(chunk)

        return resolved_path


class AIPID(str):
    """
    An id of an archival information package stored in digital
    preservation system.
    """


class DIPID(str):
    """
    An id of a dissemination information package stored in digital
    preservation system.
    """


class TransferID(str):
    """
    An id of a transfer stored in digital preservation system.
    """


class DIPFormat(Enum):
    """
    Represents a file format a dissemination information package can be
    """

    ZIP = "zip"
    TAR = "tar"


class DisseminationIDType(Enum):
    """
    Represents a method files in dissemination package are chosen.
    """

    FILE = "file"
    DIV = "div"


@dataclass
class DisseminationAIPEntry:
    aip_id: AIPID
    ids: list[str] | None = None

    def to_primitives(self) -> dict[str, str | list[str]]:
        ret: dict[str, str | list[str]] = {"aip_id": self.aip_id}
        if self.ids is not None:
            ret["ids"] = self.ids
        return ret


@dataclass
class TransferInfoResult:
    """
    Result returned from :meth:`RestClient.get_transfer` and
    /v3/<contract>/transfers/<transfer_id>
    """
    transfer_id: TransferID
    filename: str
    status: str
    actions: dict
    sip: dict
    timestamp: str


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

    def get_transfer(self, transfer_id: TransferID) -> TransferInfoResult:
        """Get transfer information from Digital Preservation Service.

        :param transfer_id: Transfer ID to fetch the information for.
        :return: Data from successful response.
        :raises HTTPError: When response code is within 400 - 599 range.
        """
        url = f"{self.base_url}/transfers/{transfer_id}"
        response = self.session.get(url)
        return TransferInfoResult(**response.json()["data"])

    def get_validation_report(
        self, transfer_id: TransferID, report_type: str = "xml"
    ) -> bytes:
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

    def delete_transfer(self, transfer_id: TransferID) -> bool:
        """Delete the given transfer information.

        This will make it so that future call to get transfer
        information or report is no longer possible.

        :param transfer_id: Transfer ID to delete.
        :return: True on success.
                 False if transfer does not exist and could not be deleted.
        """
        url = f"{self.base_url}/transfers/{transfer_id}"
        try:
            self.session.delete(url)
            return True
        except HTTPError as exc:
            if exc.response.status_code == 404:
                return False

            raise

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
        :return: SearchResuls of retrieved transfers.
        :raises HTTPError: When response code is within 400 - 599 range.
        """
        url = f"{self.base_url}/transfers"
        params = {"page": page, "limit": limit}
        if status:
            params["status"] = status
        response = self.session.get(url, params=params)
        data = response.json()["data"]

        return SearchResultV3[TransferResult].from_data(
            data=data, page=page, limit=limit, entry_type=TransferResult
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
        :return: SearchResult of matching AIPs.
        """
        params = {"page": page, "limit": limit}

        if query:
            params["q"] = query

        response = self.session.get(f"{self.base_url}/search", params=params)
        data = response.json()["data"]

        return SearchResultV3[AIPResult].from_data(
            data=data, page=page, limit=limit, entry_type=AIPResult
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
        :return: SearchResult of retrieved dissemination packages.
        :raises HTTPError: When response code is wihin 400 - 599 range.
        """
        url = f"{self.base_url}/disseminated"
        params = {"page": page, "limit": limit}
        if complete is not None:
            params['complete'] = complete

        response = self.session.get(url, params=params)
        data = response.json()["data"]

        return SearchResultV3[DIPResult].from_data(
            data=data, page=page, limit=limit, entry_type=DIPResult
        )

    def get_statistics(self) -> StatisticsResult:
        """Get the statistics overview for a contract"""
        url = f"{self.base_url}/statistics/overview"
        response = self.session.get(url)
        data = response.json()["data"]
        return StatisticsResult(
            _CapacityStats(**data["capacity"]),
            _KeyFiguresStats(**data["key_figures"]),
        )

    def get_dip_info(self, dip_id: DIPID) -> DIPInfoResult:
        """Get dissemination information from Digital Preservation Service.

        :param dip_id: The ID of the DIP
        :return: Data from successful response.
        :raises HTTPError: When response code is within 400 - 599 range.
        """
        url = f"{self.base_url}/disseminated/{dip_id}"
        response = self.session.get(url).json()["data"]
        return DIPInfoResult(**response)

    def get_dip_download_request(self, dip_id: DIPID) -> PreparedRequest:
        """
        Gets a request containing all necessary information for fetching a DIP.
        :param dip_id: ID of the dip to be downloaded
        :return: A prepared request for downloading DIP
        """
        url = f"{self.base_url}/disseminated/{dip_id}/download"
        return self.session.prepare_request(Request("GET", f"{url}"))

    def get_dip_downloader(self, dip_id: DIPID) -> DIPDownloader:
        """
        Gets a downloader for a DIP
        :param dip_id: ID of the dip to be downloaded
        :return: A DIP downloader made for specified DIP.
        """

        request = self.get_dip_download_request(dip_id)
        settings = self.session.merge_environment_settings(
            request.url, {}, None, None, None
        )
        settings["stream"] = True
        response = self.session.send(request, **settings)
        return DIPDownloader(response)

    def delete_dip(self, dip_id: DIPID) -> None:
        """Delete dissemination information package.

        :param dip_id: ID of the DIP to delete.
        :raises HTTPError: If the DIP was not deleted
        """
        url = f"{self.base_url}/disseminated/{dip_id}"
        self.session.delete(url)

    def disseminate(
        self,
        aip_list: list[DisseminationAIPEntry] | None = None,
        aip: AIPID | None = None,
        name: str | None = None,
        catalog: str | None = None,
        dip_format: DIPFormat | str | None = None,
        only_metadata: bool | None = None,
        id_type: DisseminationIDType | str | None = None,
    ) -> DIPID:
        """Make a dissemination information package.
        It is required to have either of ``aip`` or ``aip_list`` param.

        :param aip: ID of the AIP. Use this param if you are making a DIP
            from single, whole AIP.

        :param aip_list: A list of AIPs and their file
            IDs. Use this param if you are making a dip from multiple AIPs or
            want to include specific files.

        :param name: The dip will be created with this name.
        :param catalog: The version of the catalog
        :param dip_format: The file format of the resulting DIP.
        :param only_metadata: Make a package that only contains metadata.
        :param id_type: The type of IDs when selecting files.


        :return: ID of the DIP being made.

        :raises ValueError: If both or neither of ``aip_list`` and ``aip`` are
            defined.
        """

        if not ((aip_list is None) ^ (aip is None)):
            raise ValueError(
                "RestClient.disseminate: Exactly one of aip or aip_list needs"
                " to be entered"
            )

        if aip is not None:
            aip_list = [DisseminationAIPEntry(aip_id=aip)]

        body: dict = {"aips": [entry.to_primitives() for entry in aip_list]}

        if name is not None:
            body["dip_name"] = name
        if catalog is not None:
            body["catalog"] = catalog
        if dip_format is not None:
            body["format"] = DIPFormat(dip_format).value
        if only_metadata is not None:
            body["only_metadata"] = only_metadata
        if id_type is not None:
            body["id_type"] = DisseminationIDType(id_type).value

        url = f"{self.base_url}/preserved/disseminate"

        res = self.session.post(url, json=body)

        result_url = res.json()["data"]["disseminated"]
        id_string = result_url.split("/")[-1]

        return DIPID(id_string)

    def list_aip_files(
        self, aip: AIPID, page: int = 1, limit: int = 20
    ) -> SearchResultV3[AIPFileListEntry]:
        """
        Lists files inside one specific AIP. This method has paging
        functionality.

        :param aip: The id of the AIP in question
        :param page: The number of the page retrieved as integer.
        :param limit: The maximum number of the entries in paging as integer.
        :return: Search result of the retrieved file entries, which contain
            information about file paths and their ids.
        """
        url = f"{self.base_url}/preserved/{aip}/files"
        params = {"page": page, "limit": limit}

        response = self.session.get(url, params=params)
        data = response.json()["data"]

        return SearchResultV3[AIPFileListEntry].from_data(
            data=data, page=page, limit=limit, entry_type=AIPFileListEntry
        )

    def list_aip_divs(
        self, aip: AIPID, page: int = 1, limit: int = 20
    ) -> SearchResultV3[AIPDivListEntry]:
        """
        Lists information about AIP's structmap divs. This method has paging
        functionality,

        :param aip: The id of the AIP in question
        :param page: The number of the page retrieved as integer.
        :param limit: The maximum number of the entries in paging as integer.
        """
        url = f"{self.base_url}/preserved/{aip}/divs"
        params = {"page": page, "limit": limit}

        response = self.session.get(url, params=params)
        data = response.json()["data"]

        return SearchResultV3[AIPDivListEntry].from_data(
            data=data, page=page, limit=limit, entry_type=AIPDivListEntry
        )
