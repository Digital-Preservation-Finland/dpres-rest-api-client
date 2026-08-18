import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from time import sleep
from typing import Any

from requests import HTTPError

from dpres_rest_api_client import DIPRequest, AccessClient


class DisseminationCache:
    """
    A class to handling caching v2 client's DIP requests into disk.
    """

    def __init__(self):

        cache_home = os.environ.get("XDG_CACHE_HOME")
        if cache_home is not None:
            cache_dir = Path(cache_home)
        else:
            cache_dir = Path.home() / ".cache"

        dpres_cache_dir = cache_dir / "dpres-rest-api-client"

        dpres_cache_dir.mkdir(parents=True, exist_ok=True)

        self.cache_path = dpres_cache_dir / "dip_cache.json"
        self._lock = _CacheLock(dpres_cache_dir / "~dip_cache.json.lock")
        with self._lock:
            if not self.cache_path.exists():
                self._save({"cache_entries": {}})

    def get_request(
        self,
        client: AccessClient,
        path: Path,
        archive_format: str,
        catalog: str,
        delete: bool,
        aip_id: str,
    ) -> DIPRequest:
        """
        Gets a DIPRequest from cache, or if not present, makes a new one.
        """

        cache_key = self._get_cache_key(
            aip_id, archive_format, catalog, delete, path
        )
        with self._lock:
            cache_object = self._load()

            cache_entries: dict = cache_object["cache_entries"]

            if cache_key in cache_entries:
                dip_id = cache_entries[cache_key]["dip_id"]
                dip_request = DIPRequest(
                    client, aip_id, catalog, archive_format
                )
                dip_request.dip_id = dip_id

                try:
                    # The dip can be deleted from the backend, thus the cache
                    # can be out of date. In this case, just make a new
                    # request.
                    dip_request.check_status()
                except HTTPError as exc:
                    if exc.response.status_code != 404:
                        raise
                    dip_request = self._get_new_request(
                        aip_id,
                        archive_format,
                        catalog,
                        client,
                        cache_key,
                        cache_object,
                    )
            else:
                dip_request = self._get_new_request(
                    aip_id,
                    archive_format,
                    catalog,
                    client,
                    cache_key,
                    cache_object,
                )

        return dip_request

    def _get_new_request(
        self,
        aip_id,
        archive_format,
        catalog,
        client,
        cache_key: str,
        cache_object,
    ) -> Any:
        """
        Asks for a new request from the server.
        Assumes the lock is acquired
        """
        cache_created = datetime.now(timezone.utc)

        dip_request = client.create_dip_request(
            aip_id=aip_id, archive_format=archive_format, catalog=catalog
        )

        entry = {
            "created": cache_created.isoformat(),
            "dip_id": dip_request.dip_id,
        }

        cache_object["cache_entries"][cache_key] = entry
        self._save(cache_object)
        return dip_request

    @staticmethod
    def _get_cache_key(aip_id, archive_format, catalog, delete, path) -> str:
        """Gets the cache key from params. Does not need the lock."""
        return json.dumps(
            {
                "path": str(path),
                "archive_format": archive_format,
                "catalog": catalog,
                "aip_id": aip_id,
                "delete": delete,
            }
        )

    def _save(self, cache_object):
        """Saves the provided python object to the JSON file. Assumes the lock
        is acquired."""

        temp_path = self.cache_path.with_name("dip_cache.tmp")
        with temp_path.open("w") as file:
            json.dump(cache_object, file)
        temp_path.rename(self.cache_path)

    def _load(self) -> dict:
        """Loads and returns the JSON. Assumes the lock is acquired."""
        with self.cache_path.open("r") as file:
            cache_object = json.load(file)
        return cache_object

    def gc(self):
        """
        A cleanup method to remove old cache entries.
        """

        retention_time = timedelta(days=10)
        filtered = {}

        with self._lock:
            cache_object = self._load()
            entries: dict = cache_object["cache_entries"]

            for k, v in entries.items():
                if datetime.fromisoformat(v["created"]) > (
                    datetime.now(timezone.utc) - retention_time
                ):
                    filtered[k] = v

            cache_object["cache_entries"] = filtered

            self._save(cache_object)

    def remove(self, aip_id, archive_format, catalog, delete, path):
        """
        Remove specific requests from cache. This can be used when downloading
        the dip has been finished and removed from server side.
        """
        key = self._get_cache_key(
            aip_id, archive_format, catalog, delete, path
        )
        with self._lock:
            cache_object = self._load()
            entries = cache_object["cache_entries"]

            del entries[key]

            self._save(cache_object)


class _CacheLock:
    """
    A context manager to handle locking the cache file. This is implemented as
    a separate file, which's presence determines the state of the lock.
    """

    _sleeptime = 0.01
    _timeout = 5

    def __init__(self, path: Path):
        """
        :param path: A path of a lock file.
        """
        self.path = path

    def __enter__(self):
        time_waiting = 0
        while True:
            try:
                self.path.touch(exist_ok=False)
            except FileExistsError:
                pass
            else:
                break

            time_waiting += self._sleeptime
            if time_waiting >= self._timeout:
                raise TimeoutError(
                    f"Gave up on acquiring lock file {self.path}."
                    f" Please make sure there is no other processes blocking"
                    f" it and delete it if necessary."
                )

            sleep(self._sleeptime)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.path.unlink()
