"""
dpres_rest_api_client.cli tests.
"""

import json
from urllib.parse import urlencode

import pytest

import dpres_rest_api_client.cli


def test_help(cli_runner):
    """
    Test that `--help` prints the help output.
    """
    result = cli_runner(["--help"])

    # Commands are listed in the help output
    commands = ["dip", "search", "upload", "write-config"]
    for command in commands:
        assert command in result.output


def test_write_config(cli_runner, home_config_path):
    """
    Test that `write-config` creates the configuration file.
    """
    # Remove the existing file and ensure it is regenerated
    home_config_path.unlink()

    result = cli_runner(["write-config"])

    assert f"Configuration file written to {home_config_path}" in result.output
    assert home_config_path.is_file()
    assert "[dpres]" in home_config_path.read_text()

    home_config_path.write_text("overwritten config")

    # If the file exists, nothing is written at all
    result = cli_runner(["write-config"])
    assert (f"Configuration file already exists at {home_config_path}" in
            result.output)
    assert home_config_path.read_text() == "overwritten config"


def test_search(cli_runner, access_rest_api_host, requests_mock):
    """
    Test that a search can be performed.
    """
    qs_encoded = urlencode(
        {
            "page": 1,
            "limit": 1000,
        }
    )

    requests_mock.get(
        f"{access_rest_api_host}/api/3.0/urn:uuid:fake_contract_id/"
        f"search?{qs_encoded}",
        json={
            "status": "success",
            "data": {
                "results": [
                    {
                        "aip_id": "spam",
                        "content_id": None,
                        "createdate": "2021-08-01T08:59:05Z",
                        "lastmoddate": None,
                        "location": "loc",
                    },
                    {
                        "aip_id": "eggs",
                        "content_id": "eggs-contentid",
                        "createdate": "2021-08-02T09:01:58Z",
                        "lastmoddate": "2021-08-03T09:01:58Z",
                        "location": "loc",
                    },
                ],
                "links": {"self": "/"},
            },
        },
    )

    result = cli_runner(["search"])
    output = result.output

    assert "Displaying page 1 with 2 results" in output

    assert "spam" in output
    assert "2021-08-01T08:59:05Z" in output
    assert "N/A" in output

    # Get the two found entries and their columns in order
    first_line = next(
        line for line in output.split("\n") if line.startswith("spam")
    ).split(" ")
    first_line = list(filter(bool, first_line))

    second_line = next(
        line for line in output.split("\n") if line.startswith("eggs")
    ).split(" ")
    second_line = list(filter(bool, second_line))

    # Check that AIP ID, CONTENTID, creation and modification date are
    # presented in correct order
    assert first_line == ["spam", "N/A", "2021-08-01T08:59:05Z", "N/A"]
    assert second_line == [
        'eggs', 'eggs-contentid',
        '2021-08-02T09:01:58Z', '2021-08-03T09:01:58Z'
    ]


def test_search_query(cli_runner, access_rest_api_host, requests_mock):
    """
    Test performing a search with a custom query.
    """
    qs_encoded = urlencode({"page": 1, "limit": 1000, "q": "mets_OBJID:eggs"})

    requests_mock.get(
        f"{access_rest_api_host}/api/3.0/urn:uuid:fake_contract_id/"
        f"search?{qs_encoded}",
        json={
            "status": "success",
            "data": {
                "results": [
                    {
                        "aip_id": "eggs",
                        "content_id": None,
                        "createdate": "2021-08-02T09:01:58Z",
                        "lastmoddate": "2021-08-03T09:01:58Z",
                        "location": " loc",
                    }
                ],
                "links": {"self": "/"},
            },
        },
    )

    result = cli_runner(["search", "--query", "mets_OBJID:eggs"])
    output = result.output

    assert "eggs" in output
    assert "spam" not in output


def test_download(cli_runner, access_rest_api_host, requests_mock, tmp_path):
    """
    Test downloading a DIP using the `download` command.
    """
    requests_mock.post(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/"
        "preserved/spam/disseminate",
        json={
            "status": "success",
            "data": {
                "disseminated": (
                    "/api/2.0/urn:uuid:fake_contract_id/disseminated/"
                    "spam_dip"
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
    requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/"
        "disseminated/spam_dip/download",
        content=b"This is a complete DIP in a ZIP sent in a blip",
        headers={
            # requests-mock does not generate a Content-Length header
            # automatically
            "Content-Length": "46"
        },
    )
    requests_mock.delete(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/"
        "disseminated/spam_dip",
        json={
            "status": "success",
            "data": {
                "deleted": "true",
            },
        },
    )

    download_dir = tmp_path / "download"
    download_dir.mkdir()

    download_path = download_dir / "spam.zip"

    result = cli_runner(
        ["dip", "download", "--path", str(download_path), "spam"]
    )
    output = result.output

    assert f"downloading to {download_path}" in output

    # File size shown during download
    assert "Downloading (46 Bytes)" in output

    assert download_path.is_file()
    expected_bytes = b"This is a complete DIP in a ZIP sent in a blip"
    assert download_path.read_bytes() == expected_bytes

    # DIP deletion should default to True
    assert "delete" in output


@pytest.mark.parametrize(
    "params,expected_file_format,expected_name",
    (
        # Defaults to 'zip' and AIP ID as the prefix
        ([], "zip", "spam.zip"),

        # 'tar' used per filename
        (["--path", "spam.tar"], "tar", "spam.tar"),

        # 'zip' used due to manual choice despite filename
        (["--path", "spam.tar", "--archive-format", "zip"], "zip", "spam.tar"),

        # Defaults to 'zip' with filename without suffix
        (["--path", "spam"], "zip", "spam"),
    )
)
def test_download_correct_file_format(
        cli_runner, access_rest_api_host, requests_mock, tmp_path, monkeypatch,
        params, expected_file_format, expected_name):
    """
    Test downloading a DIP with `download` command using different parameters
    and ensure the correct file format and name is used in each case
    """
    requests_mock.post(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/"
        "preserved/spam/disseminate",
        json={
            "status": "success",
            "data": {
                "disseminated": (
                    "/api/2.0/urn:uuid:fake_contract_id/disseminated/"
                    "spam_dip"
                )
            },
        },
        additional_matcher=(
            lambda req: req.qs["format"][0] == expected_file_format
        )
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
    requests_mock.get(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/"
        "disseminated/spam_dip/download",
        content=b"This is a complete DIP in a ZIP sent in a blip",
        headers={
            # requests-mock does not generate a Content-Length header
            # automatically
            "Content-Length": "46"
        },
    )
    requests_mock.delete(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/"
        "disseminated/spam_dip",
        json={
            "status": "success",
            "data": {
                "deleted": "true",
            },
        },
    )

    download_dir = tmp_path / "download"
    download_dir.mkdir()

    # Change working directory to download directory to ensure they're
    # always saved there
    monkeypatch.chdir(download_dir)

    result = cli_runner(
        ["dip", "download"] + params + ["spam"]
    )
    output = result.output

    assert "downloading to " in output

    download_path = next(download_dir.iterdir())
    assert download_path.is_file()
    assert download_path.name == expected_name


def test_delete_dip_query(cli_runner, access_rest_api_host, requests_mock):
    """
    Test performing DIP deletion with both a successful deletion
    and an unsuccessful deletion.
    """
    requests_mock.delete(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/"
        "disseminated/spam_dip",
        json={
            "status": "success",
            "data": {
                "deleted": "true",
            },
        },
    )
    requests_mock.delete(
        f"{access_rest_api_host}/api/2.0/urn:uuid:fake_contract_id/"
        "disseminated/not_found_dip",
        json={
            "status": "success",
            "data": {
                "deleted": "false",
            },
        },
    )

    # Successful deletion
    result = cli_runner(["dip", "delete", "spam_dip"])
    output = result.output
    assert "Proceeding to delete" in output

    # Unsuccessful deletion
    result = cli_runner(["dip", "delete", "not_found_dip"])
    output = result.output
    assert "Proceeding to delete" in output
    assert "DIP could not be deleted" in output


@pytest.mark.parametrize(
    "enable_resumable",
    [
        False,
        True,
    ],
    ids=["Normal use", "Resumable enabled"],
)
@pytest.mark.usefixtures("mock_tus_endpoints")
def test_upload_file(
    cli_runner, transfer_id, uploadable_file_fx, enable_resumable
):
    """Test that the click-application can upload file."""
    commands = ["upload", "--chunk-size", "3", f"{uploadable_file_fx}"]
    if enable_resumable:
        commands.append("--enable-resumable")
    result = cli_runner(commands)
    assert result.exit_code == 0
    assert f"{transfer_id}" in result.output


@pytest.mark.usefixtures("mock_tus_endpoints")
def test_upload_empty_file(cli_runner, empty_file_fx):
    """Test that the click-application can handle an empty file."""
    commands = ["upload", f"{empty_file_fx}"]
    result = cli_runner(commands)
    assert result.exit_code == 1
    assert "file is empty" in result.output


@pytest.mark.usefixtures("mock_tus_endpoints")
def test_upload_wrong_file_ending(cli_runner, wrong_file_ending_fx):
    """Test that the click-application can handle a file with invalid suffix"""
    commands = ["upload", f"{wrong_file_ending_fx}"]
    result = cli_runner(commands)
    assert result.exit_code == 1
    assert "format not supported" in result.output


@pytest.mark.usefixtures("mock_access_rest_api_v3_endpoints")
@pytest.mark.parametrize(
    ("transfer_id", "transfer_exists"),
    [
        ("sip.tar-00000000-0000-0000-0000-000000000001", True),
        ("sip.tar-00000000-0000-0000-0000-000000000002", True),
        ("sip.tar-99999999-9999-9999-9999-999999999999", False),
    ],
    ids=["Get transfer", "Get transfer in progress", "No transfer"],
)
def test_transfers_info(cli_runner, transfer_id, transfer_exists):
    """Test that the click-application can get transfer info."""
    commands = ["transfer", "info", f"{transfer_id}"]
    result = cli_runner(commands)
    if transfer_exists:
        assert result.exit_code == 0
        assert f"{transfer_id}" in result.output
    else:
        assert result.exit_code == 1


@pytest.mark.usefixtures("mock_access_rest_api_v3_endpoints")
@pytest.mark.parametrize(
    ("transfer_id", "transfer_exists", "output_file"),
    [
        ("sip.tar-00000000-0000-0000-0000-000000000001", True, False),
        ("sip.tar-00000000-0000-0000-0000-000000000001", True, True),
        ("sip.tar-99999999-9999-9999-9999-999999999999", False, True),
    ],
    ids=["Write to default", "Write to custom", "No report"],
)
def test_transfers_get_report(
    cli_runner, transfer_id, transfer_exists, output_file, tmp_path,
    monkeypatch,
):
    """Test that the click-application can get transfer report."""

    def _mock_resolve(_):
        """Make Path(".").resolve() return tmp_path."""
        return tmp_path

    commands = ["transfer", "get-report", f"{transfer_id}"]
    if output_file:
        report_path = tmp_path / "report.xml"
        commands.append("--path")
        commands.append(f"{report_path}")
    else:
        monkeypatch.setattr(
            dpres_rest_api_client.cli.Path, "resolve", _mock_resolve)
        report_path = tmp_path / f"{transfer_id}-report.xml"

    result = cli_runner(commands)
    if not transfer_exists:
        assert result.exit_code == 1
        # Conclude testing here.
        return

    assert result.exit_code == 0

    assert f"{report_path}" in result.output
    assert report_path.is_file()


@pytest.mark.usefixtures("mock_access_rest_api_v3_endpoints")
@pytest.mark.parametrize(
    "params,expected_file_type,expected_name",
    (
        # Defaults to 'xml' and transfer ID as the prefix
        ([], "xml", "sip.tar-00000000-0000-0000-0000-000000000001-report.xml"),

        # 'html' used per filename
        (["--path", "sip.html"], "html", "sip.html"),

        # 'html' used due to manual choice despite filename
        (["--path", "sip.xml", "--file-type", "html"], "html", "sip.xml"),

        # Defaults to 'xml' with filename without suffix
        (["--path", "sip"], "xml", "sip"),

    )
)
def test_transfers_get_report_correct_file_format(
        cli_runner, requests_mock, tmp_path, monkeypatch,
        params, expected_file_type, expected_name):
    """
    Test downloading a DIP with `download` command using different parameters
    and ensure the correct file format and name is used in each case
    """
    transfer_id = "sip.tar-00000000-0000-0000-0000-000000000001"
    monkeypatch.chdir(tmp_path)

    report_path = tmp_path / expected_name

    result = cli_runner(["transfer", "get-report", transfer_id] + params)

    assert result.exit_code == 0
    assert report_path.is_file()

    last_request = requests_mock.request_history[-1]

    # The expected file type was used to generate the report
    assert last_request.qs["type"] == [expected_file_type]


@pytest.mark.usefixtures("mock_access_rest_api_v3_endpoints")
@pytest.mark.parametrize(
    ("transfer_id", "transfer_exists"),
    [
        ("sip.tar-00000000-0000-0000-0000-000000000001", True),
        ("sip.tar-99999999-9999-9999-9999-999999999999", False),
    ],
    ids=["Delete transfer", "No transfer"],
)
def test_transfers_delete(cli_runner, transfer_id, transfer_exists):
    """Test that the click-application can get transfer info."""
    commands = ["transfer", "delete", f"{transfer_id}"]
    result = cli_runner(commands)
    if transfer_exists:
        assert result.exit_code == 0
        assert f"{transfer_id}" in result.output
    else:
        assert result.exit_code == 1


@pytest.mark.usefixtures("mock_access_rest_api_v3_list_endpoint")
def test_transfers_list(cli_runner):
    """Test that the click-application can list the transfers."""
    commands = ["transfer", "list"]
    result = cli_runner(commands)
    assert result.exit_code == 0
    assert "accepted" in result.output


@pytest.mark.parametrize(
    "response_text",
    [
        json.dumps(
            {
                "data": {"message": "I'm a teapot in json format",
                         "random_key": "Some message involved with this key"},
                "status": "fail",
            }
        ),
        "I'm a teapot in text format",
    ],
    ids=["Expected response format", "Unexpected response format"],
)
def test_transfers_list_errors(
    cli_runner, access_rest_api_host, contract_id, requests_mock, response_text
):
    """Test that the click-application handles error responses when
    attempting to list transfers.
    """
    commands = ["transfer", "list"]

    requests_mock.get(
        f"{access_rest_api_host}/api/3.0/{contract_id}/transfers",
        text=response_text,
        status_code=418,
    )

    result = cli_runner(commands)
    assert result.exit_code == 1
    assert "Error:" in result.output


def test_statistics(
    cli_runner, access_rest_api_host, contract_id, requests_mock
):
    """Test fetching statistics.

    :param cli_runner: Function that runs dpres-client command
    :param access_rest_api_host: Access REST API host
    :param contract_id: Contract identifier
    """
    requests_mock.get(
        f"{access_rest_api_host}/api/3.0/{contract_id}/statistics/overview",
        json={
            "status": "success",
            "data": {
                "capacity": {
                    "used": 1,
                    "available": 2097152,  # 2 MiB
                    "total": 3000000,  # 3 MB ≈ 2.9 MiB
                },
                "key_figures": {
                    "sips_accepted": 4,
                    "objects_preserved": 5,
                }
            }
        }
    )

    result = cli_runner(["statistics"])
    assert result.output == (
        "Capacity used: 1 Byte\n"
        "Capacity available: 2.0 MiB\n"
        "Total capacity: 2.9 MiB\n"
        "Accepted sips: 4\n"
        "Preserved objects: 5\n"
    )
    assert result.exit_code == 0
