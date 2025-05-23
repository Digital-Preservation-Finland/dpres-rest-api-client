# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-05-21
### Changed
 - Renamed the project to dpres-rest-api-client. The v3 api does more than just accessing.
 - Renamed command line tool to dpres-client
 - Moved the project to use semantic versioning

### Removed
 - Removed RPM packaging for RHEL 7 and 8

## [0.8] - 2025-05-08
### Changed
 - Catch HTTP Error exception during client command transfer list
 - Change TUS storage cache file to generate at user's HOME folder when using client command
 - Removed ingest-report client command. This is superseded by transfer client command. 
 - Change text output when using client command for downloading transfer validation report
 - Update README.rst to contain more information on client and class usage.

## [0.7] - 2025-04-16
### Added
 - Client command for uploading transfer
 - Client command for getting transfer info
 - Client command for downloading transfer validation report
 - Client command for deleting transfer info and report
 - Client command for listing transfers

## [0.6] - 2024-04-03
### Added
 - Installation instructions for AlmaLinux 9 using RPM packages

## [0.5] - 2023-07-20
### Added
 - Add RHEL9 RPM spec file.

## [0.4] - 2022-03-31
### Changed
- Changed `get_ingest_report_entries` to return an empty list instead of raising 404 HTTP error when no ingest reports are found.
- Changed `get_ingest_report` to return None of raising 404 HTTP error when no ingest report is found.

## [0.3] - 2022-02-21
### Added
 - Add `AccessClient.contract_id` property
 - Add `DIPRequest.dip_id` property
 - Add the functionality to fetch ingest reports as three new methods in the `AccessClient` class: `get_ingest_report_entries`, `get_ingest_report` and `get_latest_ingest_report`.
 - Add the functionality to fetch ingest reports to the CLI.

### Changed
 - `DIPRequest.poll` renamed to `DIPRequest.check_status`
 - `DIPRequest.poll` argument `block` renamed to `poll`
 - Changed CLI commands `download` and `delete` to be grouped under the command `dip`

## [0.2] - 2022-01-04

 - No user-facing changes

## 0.1 - 2021-10-16
### Added
 - First release of dpres-access-rest-api-client

[1.0.0]: https://github.com/Digital-Preservation-Finland/dpres-rest-api-client/compare/v0.8...v1.0.0
[0.8]: https://github.com/Digital-Preservation-Finland/dpres-rest-api-client/compare/v0.7...v0.8
[0.7]: https://github.com/Digital-Preservation-Finland/dpres-rest-api-client/compare/v0.6...v0.7
[0.6]: https://github.com/Digital-Preservation-Finland/dpres-rest-api-client/compare/v0.5...v0.6
[0.5]: https://github.com/Digital-Preservation-Finland/dpres-rest-api-client/compare/v0.4...v0.5
[0.4]: https://github.com/Digital-Preservation-Finland/dpres-rest-api-client/compare/v0.3...v0.4
[0.3]: https://github.com/Digital-Preservation-Finland/dpres-rest-api-client/compare/v0.2...v0.3
[0.2]: https://github.com/Digital-Preservation-Finland/dpres-rest-api-client/compare/v0.1...v0.2
[Unreleased]: https://github.com/Digital-Preservation-Finland/dpres-rest-api-client/compare/v1.0.0...HEAD
