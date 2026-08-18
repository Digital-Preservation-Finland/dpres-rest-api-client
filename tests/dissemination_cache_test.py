import json

import pytest

from dpres_rest_api_client._dissemination_cache import DisseminationCache


def test_request_two_times(
    client_v2,
    dissemination_cache_path,
    access_rest_api_host,
    requests_mock,
    tmp_path,
):
    mock_post = requests_mock.post(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/"
        "preserved/spam/disseminate",
        json={
            "status": "success",
            "data": {
                "disseminated": (
                    "/api/2.0/urn:uuid:fake_contract_id/disseminated/spam_dip"
                )
            },
        },
    )
    mock_get = requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/"
        "disseminated/spam_dip",
        json={
            "status": "success",
            "data": {
                "complete": "true",
                "actions": {
                    "download": (
                        "/api/2.0/urn:uuid:fake_contract_id/disseminated/"
                        "spam_dip/download"
                    )
                },
            },
        },
    )

    dip_cache = DisseminationCache()

    archive_format = "zip"
    catalog = None
    delete = True
    aip_id = "spam"

    dip_cache.get_request(
        client_v2, tmp_path, archive_format, catalog, delete, aip_id
    )
    dip_cache.get_request(
        client_v2, tmp_path, archive_format, catalog, delete, aip_id
    )

    assert mock_post.called_once
    assert mock_get.called_once


def test_remove_from_cache(
    dissemination_cache_path,
    tmp_path,
    client_v2,
    requests_mock,
    access_rest_api_host,
):
    requests_mock.post(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/"
        "preserved/spam/disseminate",
        json={
            "status": "success",
            "data": {
                "disseminated": (
                    "/api/2.0/urn:uuid:fake_contract_id/disseminated/spam_dip"
                )
            },
        },
    )

    requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/"
        "disseminated/spam_dip",
        json={
            "status": "success",
            "data": {
                "complete": "true",
                "actions": {
                    "download": (
                        "/api/2.0/urn:uuid:fake_contract_id/disseminated/"
                        "spam_dip/download"
                    )
                },
            },
        },
    )

    dip_cache = DisseminationCache()

    archive_format = "zip"
    catalog = None
    delete = True
    aip_id = "spam"

    dip_cache.get_request(
        client_v2, tmp_path, archive_format, catalog, delete, aip_id
    )

    with dissemination_cache_path.open("r") as file:
        loaded = json.load(file)
    assert len(loaded["cache_entries"]) == 1

    dip_cache.remove(aip_id, archive_format, catalog, delete, tmp_path)

    with dissemination_cache_path.open("r") as file:
        loaded = json.load(file)
    assert len(loaded["cache_entries"]) == 0


@pytest.mark.freeze_time("2025-07-31T10:00:00+00:00")
def test_gc(dissemination_cache_path):

    cache = DisseminationCache()
    with dissemination_cache_path.open("w") as file:
        json.dump(
            {
                "cache_entries": {
                    "unimportant_key1": {
                        "created": "2000-01-01T00:00:00+00:00",
                        "dip_id": "unimportant_id_1",
                    },
                    "unimportant_key2": {
                        "created": "2025-07-31T09:00:00+00:00",
                        "dip_id": "unimportant_id_2",
                    },
                }
            },
            file,
        )

    with dissemination_cache_path.open("r") as file:
        loaded = json.load(file)
    assert len(loaded["cache_entries"]) == 2

    cache.gc()

    with dissemination_cache_path.open("r") as file:
        loaded = json.load(file)

    assert len(loaded["cache_entries"]) == 1


def test_deleted_from_backend_retry(
    access_rest_api_host,
    requests_mock,
    dissemination_cache_path,
    client_v2,
    tmp_path,
):
    cache = DisseminationCache()

    archive_format = "zip"
    catalog = None
    delete = True
    aip_id = "spam"

    key = cache._get_cache_key(
        aip_id, archive_format, catalog, delete, tmp_path
    )

    mock_get_fail = requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/disseminated/spam_dip1",
        status_code=404,
    )

    mock_post = requests_mock.post(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/"
        "preserved/spam/disseminate",
        json={
            "status": "success",
            "data": {
                "disseminated": (
                    "/api/2.0/urn:uuid:fake_contract_id/disseminated/spam_dip2"
                )
            },
        },
    )

    with dissemination_cache_path.open("w") as file:
        json.dump(
            {
                "cache_entries": {
                    key: {
                        "created": "2000-01-01T00:00:00+00:00",
                        "dip_id": "spam_dip1",
                    },
                }
            },
            file,
        )

    request = cache.get_request(
        client_v2, tmp_path, archive_format, catalog, delete, aip_id
    )

    assert mock_get_fail.called_once
    assert mock_post.called_once

    assert request.dip_id == "spam_dip2"

    with dissemination_cache_path.open("r") as file:
        loaded = json.load(file)

    assert len(loaded["cache_entries"]) == 1

