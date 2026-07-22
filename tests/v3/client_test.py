"""Module that tests dpres_rest_api_client.v3.client."""
import re
from base64 import b64encode
from pathlib import Path
from urllib.parse import urlencode

import pytest
from dpres_rest_api_client.v3.client import (
    RestClient,
    SearchResultV3,
    AIPID,
    DIPID,
    DisseminationAIPEntry,
    DisseminationIDType,
    DIPFormat,
    TransferID,
    StatisticsResult,
    _CapacityStats,
    _KeyFiguresStats,
    AIPResult,
    TransferResult,
    DIPResult,
)
from requests.exceptions import HTTPError
from requests_mock import mocker


@pytest.mark.usefixtures("mock_tus_endpoints")
def test_upload(client_v3, uploadable_file_fx):
    """Test that we can upload without issue.

    The store_url is intentionally set to False so that we won't trigger
    tuspy's implementation of file storage cache.
    """
    uploader = client_v3.create_uploader(
        file_path=str(uploadable_file_fx), chunk_size=3, store_url=False
    )
    uploader.upload_chunk()
    uploader.upload()


@pytest.mark.usefixtures("mock_access_rest_api_v3_endpoints")
@pytest.mark.parametrize(
    ("transfer_id", "transfer_exists"),
    [
        ("sip.tar-00000000-0000-0000-0000-000000000001", True),
        ("sip.tar-00000000-0000-0000-0000-000000000002", True),
        ("sip.tar-99999999-9999-9999-9999-999999999999", False),
    ],
    ids=["Get transfer",
         "Get transfer in progress",
         "Unauthorized access attempt"],
)
def test_get_transfer(client_v3, transfer_id, transfer_exists):
    """Test that we can get specific transfer and status is readable."""
    if transfer_exists:
        transfer = client_v3.get_transfer(TransferID(transfer_id))
        assert transfer
        assert transfer["status"]
    else:
        with pytest.raises(HTTPError):
            client_v3.get_transfer(TransferID(transfer_id))


@pytest.mark.usefixtures("mock_access_rest_api_v3_endpoints")
@pytest.mark.parametrize(
    ("transfer_id", "report_exists"),
    [
        ("sip.tar-00000000-0000-0000-0000-000000000001", True),
        ("sip.tar-99999999-9999-9999-9999-999999999999", False),
    ],
    ids=["Get report", "Unauthorized access attempt"],
)
def test_get_validation_report(client_v3, transfer_id, report_exists):
    """Test that we can get specific transfer's report to download."""
    if report_exists:
        report = client_v3.get_validation_report(TransferID(transfer_id))
        assert report
    else:
        with pytest.raises(HTTPError):
            client_v3.get_validation_report(TransferID(transfer_id))


@pytest.mark.usefixtures("mock_access_rest_api_v3_endpoints")
@pytest.mark.parametrize(
    ("transfer_id", "expected_success"),
    [
        ("sip.tar-00000000-0000-0000-0000-000000000001", True),
        ("sip.tar-99999999-9999-9999-9999-999999999999", False),
    ],
    ids=["Delete transfer", "Unauthorized deletion attempt"],
)
def test_delete_transfer(client_v3, transfer_id, expected_success):
    """Test that we can delete the transfer information and their reports."""
    success = client_v3.delete_transfer(TransferID(transfer_id))
    assert success is expected_success


@pytest.mark.usefixtures("mock_access_rest_api_v3_list_endpoint")
@pytest.mark.parametrize(
    ("page", "limit", "expected_count", "has_next"),
    [
        (None, None, 20, False),
        (None, 5, 5, True),
        (2, 5, 5, True),
    ],
    ids=["Normal listing", "Limited listing", "Page 2"],
)
def test_list_transfers_paging(
    client_v3, page, limit, expected_count, has_next
):
    """Test that we can get list of recent transfers."""
    search_result = client_v3.list_transfers(page=page, limit=limit)

    assert len(search_result.results) == expected_count
    assert search_result.page == page
    assert search_result.limit == limit
    assert search_result.has_next_page == has_next


@pytest.mark.usefixtures("mock_access_rest_api_v3_list_endpoint")
@pytest.mark.parametrize("status", [None, "accepted"])
def test_list_transfers(client_v3, status):
    """Test retrieving transfers, with and without status filtering"""
    search_result = client_v3.list_transfers(status=status)

    if status is None:
        # No status filtering, transfers of every status are returned
        found_statuses = {entry.status for entry in search_result.results}
        assert found_statuses == {
            "accepted", "in_progress", "rejected", "uploading"
        }
    else:
        # Status filtering active, only transfers of one status returned
        assert all(entry.status == status for entry in search_result.results)

    # Test that the results contain correct typing
    assert all(
        isinstance(entry, TransferResult) for entry in search_result.results
    )
    assert all(
        isinstance(entry.transfer_id, TransferID)
        for entry in search_result.results
    )

@pytest.mark.parametrize(
    "qs",
    [None, {"complete": False, "page": "page-param", "limit": "limit-param"}],
)
def test_list_dips(requests_mock, client_v3, qs, access_rest_api_host, contract_id):
    """
    Test ``list_dips`` function.
    Using a mock call to access_rest_api, check that the query string is passed correctly
    and the response from ``list_dips`` is correct.
    """

    complete_status = True if qs is None else qs["complete"]
    url = f"{access_rest_api_host}/api/3.0/{contract_id}/disseminated"
    mock_results = [
        {
            "dip_id": f"dip_id_{i}",
            "complete": complete_status,
            "disseminated": url,
            "actions": ({"download": f"{url}/download"} if complete_status else {}),
            "timestamp": "2024-11-15T10_10_00Z",
        }
        for i in range(5)
    ]

    expected_return = [
        DIPResult(
            DIPID(f"dip_id_{i}"),
            complete_status,
            url,
            {"download": f"{url}/download"} if complete_status else {},
            "2024-11-15T10_10_00Z",
        )
        for i in range(5)
    ]

    access_rest_api_mock = requests_mock.get(
        url,
        json={
            "data": {
                "links": {"previous": "prev_value", "next": "next_value"},
                "results": mock_results,
            }
        },
    )

    search_result = client_v3.list_dips() if qs is None else client_v3.list_dips(**qs)

    # Client does not change the format of the results
    assert search_result.results == expected_return

    query_string = access_rest_api_mock.last_request.qs
    if qs is None:
        # Default parameters are passed correctly
        assert "complete" not in query_string
        assert query_string["page"][0] == str(1)
        assert query_string["limit"][0] == str(20)
    else:
        # Given parameters are passed correctly
        assert query_string["complete"][0] == str(qs["complete"]).lower()
        assert query_string["page"][0] == qs["page"]
        assert query_string["limit"][0] == qs["limit"]

    # Test that the results contain correct typing
    assert all(isinstance(entry, DIPResult) for entry in search_result.results)
    assert all(
        isinstance(entry.dip_id, DIPID) for entry in search_result.results
    )


def _create_search_result(results, next=None, previous=None):
    return {
        "status": "success",
        "data": {
            "results": results,
            "links": {
                "self": "/",
                "next": next,
                "previous": previous
            }
        }
    }


@pytest.mark.parametrize(
    "page,query,expected",
    [
        (
            None, None,
            SearchResultV3(
                results=[
                    AIPResult(
                        aip_id=AIPID("aip_id_1"),
                        content_id="content_id_1",
                        createdate="2026-01-01T12:00:00Z",
                        lastmoddate=None,
                        location="loc",
                        match=None,
                    ),
                    AIPResult(
                        aip_id=AIPID("aip_id_1_v2"),
                        content_id=None,
                        createdate="2026-01-01T12:00:00Z",
                        lastmoddate="2026-01-02T12:00:00Z",
                        location="loc",
                        match=None,
                    ),
                ],
                has_next_page=True,
                page=1,
                limit=1000
            ),
        ),
        (
            2, None,
            SearchResultV3(
                results=[
                    AIPResult(
                        aip_id=AIPID("aip_id_2"),
                        content_id="content_id_2",
                        createdate="2026-02-01T12:00:00Z",
                        lastmoddate=None,
                        location="loc",
                        match=None,
                    )
                ],
                has_next_page=False,
                page=2,
                limit=1000
            )
        ),
        (
            None, "file_id:aip_id_3",
            SearchResultV3(
                results=[
                    AIPResult(
                        aip_id=AIPID("aip_id_3"),
                        content_id="content_id_3",
                        createdate="2026-02-01T12:00:00Z",
                        lastmoddate=None,
                        location="loc",
                        match=None,
                    )
                ],
                has_next_page=False,
                page=1,
                limit=1000
            )
        )
    ]
)
def test_search(
        client_v3, access_rest_api_host, contract_id,
        requests_mock, page, query, expected):
    """Test that correct results are returned for each set of parameters"""
    requests_mock.get(
        f"{access_rest_api_host}/api/3.0/{contract_id}/search",
        json=_create_search_result(
            [
                {
                    "aip_id": "aip_id_1",
                    "content_id": "content_id_1",
                    "createdate": "2026-01-01T12:00:00Z",
                    "lastmoddate": None,
                    "location": "loc",
                },
                {
                    "aip_id": "aip_id_1_v2",
                    "content_id": None,
                    "createdate": "2026-01-01T12:00:00Z",
                    "lastmoddate": "2026-01-02T12:00:00Z",
                    "location": "loc",
                },
            ],
            next="?page=2",
        ),
    )
    requests_mock.get(
        f"{access_rest_api_host}/api/3.0/{contract_id}/search?page=2",
        json=_create_search_result(
            [
                {
                    "aip_id": "aip_id_2",
                    "content_id": "content_id_2",
                    "createdate": "2026-02-01T12:00:00Z",
                    "lastmoddate": None,
                    "location": "loc",
                }
            ],
            previous="?page=1",
        ),
    )
    requests_mock.get(
        f"{access_rest_api_host}/api/3.0/{contract_id}/search"
        f"?{urlencode({'q': 'file_id:aip_id_3'})}",
        json=_create_search_result(
            [
                {
                    "aip_id": "aip_id_3",
                    "content_id": "content_id_3",
                    "createdate": "2026-02-01T12:00:00Z",
                    "lastmoddate": None,
                    "location": "loc",
                }
            ]
        ),
    )

    params = {}
    if page is not None:
        params["page"] = page
    if query is not None:
        params["query"] = query

    search_result = client_v3.search(**params)

    assert search_result.results == expected.results
    assert search_result.has_next_page == expected.has_next_page
    assert search_result.page == expected.page

    # Test that the results contain correct typing
    assert all(
        isinstance(entry.aip_id, AIPID) for entry in search_result.results
    )


def test_statistics_success(
    client_v3: RestClient,
    requests_mock: mocker.Mocker,
    access_rest_api_host: str,
    contract_id: str,
) -> None:
    """Test that statistics_overview returns correctly parsed data."""
    url = f"{access_rest_api_host}/api/3.0/{contract_id}/statistics/overview"

    api_response = {
        "data": {
            "capacity": {
                "used": 100,
                "available": 900,
                "total": 1000,
            },
            "key_figures": {
                "sips_accepted": 42,
                "objects_preserved": 1337,
            },
        },
        "status": "success",
    }

    expected = StatisticsResult(
        _CapacityStats(used=100, available=900, total=1000),
        _KeyFiguresStats(sips_accepted=42, objects_preserved=1337),
    )

    mock = requests_mock.get(url, json=api_response, status_code=200)

    result = client_v3.get_statistics()

    assert result == expected
    assert mock.called
    assert mock.call_count == 1


def test_get_dip_info(
    client_v3, access_rest_api_host, contract_id, requests_mock
):
    """
    Test the get_dip_info method. Make sure it sends the request and
    the returned data is correct.
    """

    dip_id = "dip_id"
    complete = True
    download_url = f"{access_rest_api_host}/api/3.0/{contract_id}/disseminated/{dip_id}/download"
    actions = {"download": download_url}
    dip = {"dip_name": "testname"}
    timestamp = "2026-02-01T12:00:00Z"

    requests_mock.get(
        f"{access_rest_api_host}/api/3.0/{contract_id}/disseminated/{dip_id}",
        json={
            "status": "success",
            "data": {
                "dip_id": dip_id,
                "complete": complete,
                "actions": actions,
                "dip": dip,
                "timestamp": timestamp,
            },
        },
    )

    dip_info = client_v3.get_dip_info(dip_id)

    assert dip_info.dip_id == dip_id
    assert dip_info.complete == complete
    assert dip_info.actions == actions
    assert dip_info.dip == dip
    assert dip_info.timestamp == timestamp
    assert dip_info.dip["dip_name"] == "testname"


def test_download_dip_request(
    client_v3: RestClient,
    access_rest_api_host: str,
    contract_id: str,
):
    """Test that the DIP request contains right values"""
    dip_id = "testid"
    request = client_v3.get_dip_download_request(dip_id)
    assert (
        request.url
        == f"{access_rest_api_host}/api/3.0/{contract_id}/disseminated/{dip_id}/download"
    )

    assert "Authorization" in request.headers

    auth_token = (b64encode(b"fakeuser:fakepassword")).decode()

    assert request.headers["Authorization"] == "Basic " + auth_token


def test_download_dip(
    client_v3: RestClient,
    requests_mock: mocker.Mocker,
    access_rest_api_host: str,
    contract_id: str,
    tmp_path: Path,
) -> None:
    """Test that dip gets downloaded into a file."""

    dip_id = "testid"
    url = f"{access_rest_api_host}/api/3.0/{contract_id}/disseminated/{dip_id}/download"

    data = b"abc"

    filename = "testtar.tar"

    requests_mock.get(
        url,
        content=data,
        status_code=200,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )

    downloader = client_v3.get_dip_downloader(DIPID(dip_id))
    downloader.save(tmp_path / downloader.suggested_filename)

    expected_path = tmp_path / filename

    assert downloader.suggested_filename == filename
    assert expected_path.exists()

    with open(expected_path, "rb") as file:
        read_contents = file.read()

    assert read_contents == data


def test_stream_dip(
    client_v3: RestClient,
    requests_mock: mocker.Mocker,
    access_rest_api_host: str,
    contract_id: str,
) -> None:
    """Test that dip download can be streamed with iterators."""

    dip_id = "testid"
    url = f"{access_rest_api_host}/api/3.0/{contract_id}/disseminated/{dip_id}/download"
    data = b"abc"

    requests_mock.get(
        url,
        content=data,
        status_code=200,
        headers={"Content-Disposition": "attachment; filename=testtar.tar"},
    )

    downloader = client_v3.get_dip_downloader(DIPID(dip_id))
    resulting_bytes_iterator = downloader.download_iter

    assert data == b"".join(resulting_bytes_iterator)


@pytest.mark.parametrize(
    ("dip_id", "expected_status_code"),
    [("testid1", 204), ("testid2", 404)],
)
def test_delete_dip(
    client_v3: RestClient,
    requests_mock: mocker.Mocker,
    access_rest_api_host: str,
    contract_id: str,
    dip_id: str,
    expected_status_code: int
) -> None:
    """Test that DIPs are deleted. Successful deletes have response code 204.
    4xx and 5xx codes raise exception."""

    url = f"{access_rest_api_host}/api/3.0/{contract_id}/disseminated/{dip_id}"
    delete = requests_mock.delete(url, status_code=expected_status_code)

    if expected_status_code == 204:
        client_v3.delete_dip(DIPID(dip_id))
        assert delete.called_once
    else:
        with pytest.raises(HTTPError) as e:
            client_v3.delete_dip(DIPID(dip_id))
        assert delete.called_once
        assert e.value.response.status_code == expected_status_code


@pytest.mark.parametrize(
    ("method_args", "expected_request"),
    [
        (
            {"aip": AIPID("test_aip_id_1")},
            {"aips": [{"aip_id": "test_aip_id_1"}]},
        ),
        (
            {
                "aip_list": [
                    DisseminationAIPEntry(
                        AIPID("test_aip_id_2"), ["0", "1", "2"]
                    )
                ],
                "id_type": DisseminationIDType.DIV,
            },
            {
                "aips": [{"aip_id": "test_aip_id_2", "ids": ["0", "1", "2"]}],
                "id_type": "div",
            },
        ),
        (
            {"aip": AIPID("test_aip_id_3"), "name": "testname"},
            {"aips": [{"aip_id": "test_aip_id_3"}], "dip_name": "testname"},
        ),
        (
            {"aip": AIPID("test_aip_id_4"), "catalog": "1.8"},
            {"aips": [{"aip_id": "test_aip_id_4"}], "catalog": "1.8"},
        ),
        (
            {"aip": AIPID("test_aip_id_5"), "dip_format": DIPFormat.TAR},
            {"aips": [{"aip_id": "test_aip_id_5"}], "format": "tar"},
        ),
        (
            {"aip": AIPID("test_aip_id_6"), "only_metadata": True},
            {"aips": [{"aip_id": "test_aip_id_6"}], "only_metadata": True},
        ),
    ],
)
def test_disseminate(
    client_v3: RestClient,
    requests_mock: mocker.Mocker,
    access_rest_api_host: str,
    contract_id: str,
    method_args,
    expected_request,
) -> None:
    """Tests that RestClient.disseminate makes right kind of HTTP requests with
    correct format, with different parameters.
    """

    url = f"{access_rest_api_host}/api/3.0/{contract_id}/preserved/disseminate"

    new_dip_id = "test_dip_id_123"
    new_dip_url = (
        f"{access_rest_api_host}/api/3.0/{contract_id}/disseminated/"
        f"{new_dip_id}"
    )

    post = requests_mock.post(
        url,
        status_code=202,
        json={"status": "success", "data": {"disseminated": new_dip_url}},
    )

    returned_dip_id = client_v3.disseminate(**method_args)

    assert returned_dip_id == new_dip_id
    assert isinstance(returned_dip_id, DIPID)

    assert post.called_once
    assert post.last_request.qs == {}

    assert post.last_request.json() == expected_request


def test_disseminate_conflicting_params(
    client_v3: RestClient,
    requests_mock: mocker.Mocker,
    access_rest_api_host: str,
    contract_id: str,
):
    """Tests that providing both aip and aip_list parameters to
    RestClient.disseminate does not fail silently.
    """
    url = f"{access_rest_api_host}/api/3.0/{contract_id}/preserved/disseminate"
    new_dip_url = (
        f"{access_rest_api_host}/api/3.0/{contract_id}/disseminated/"
        "test_dip_id_123"
    )
    requests_mock.post(
        url,
        status_code=202,
        json={"status": "success", "data": {"disseminated": new_dip_url}},
    )

    match = re.compile(r"^(?=.*\baip_list\b)(?=.*\baip\b).*$")

    with pytest.raises(ValueError, match=match):
        client_v3.disseminate(
            aip=AIPID("test_aip_id_1"),
            aip_list=[
                DisseminationAIPEntry(AIPID("test_aip_id_2"), ["0", "1", "2"])
            ],
        )
