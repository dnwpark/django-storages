"""Vercel Blob storage backend for Django."""

import mimetypes
from io import BytesIO
from shutil import copyfileobj
from tempfile import SpooledTemporaryFile

import requests
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import File

from storages.base import BaseStorage
from storages.utils import check_location
from storages.utils import clean_name
from storages.utils import safe_join
from storages.utils import setting

VERCEL_BLOB_API_URL = "https://blob.vercel-storage.com"


class VercelBlobException(Exception):
    pass


class VercelBlobFile(File):
    def __init__(self, name, storage):
        self.name = name
        self._storage = storage
        self._file = None

    def _get_file(self):
        if self._file is None:
            self._file = SpooledTemporaryFile()
            response = self._storage._make_request("GET", self._storage.url(self.name))
            response.raise_for_status()
            with BytesIO(response.content) as content:
                copyfileobj(content, self._file)
            self._file.seek(0)
        return self._file

    def _set_file(self, value):
        self._file = value

    file = property(_get_file, _set_file)


class VercelBlobStorage(BaseStorage):
    """Vercel Blob Storage backend for Django."""

    def __init__(self, **settings):
        super().__init__(**settings)
        if not self.token:
            raise ImproperlyConfigured(
                "VercelBlobStorage requires a token. Set VERCEL_BLOB_TOKEN in your "
                "Django settings or the BLOB_READ_WRITE_TOKEN environment variable."
            )
        if self.default_acl not in ("public", "private"):
            raise ImproperlyConfigured(
                "VERCEL_BLOB_DEFAULT_ACL must be 'public' or 'private'."
            )
        check_location(self)

    def get_default_settings(self):
        return {
            "token": setting("VERCEL_BLOB_TOKEN"),
            "location": setting("VERCEL_BLOB_LOCATION", ""),
            "base_url": setting("VERCEL_BLOB_BASE_URL"),
            "default_acl": setting("VERCEL_BLOB_DEFAULT_ACL", "public"),
            "allow_overwrite": setting("VERCEL_BLOB_ALLOW_OVERWRITE", False),
            "cache_control_max_age": setting("VERCEL_BLOB_CACHE_CONTROL_MAX_AGE"),
            "add_random_suffix": setting("VERCEL_BLOB_ADD_RANDOM_SUFFIX", False),
        }

    def _make_request(self, method, url, **kwargs):
        headers = kwargs.pop("headers", {})
        headers["authorization"] = f"Bearer {self.token}"
        return requests.request(method, url, headers=headers, **kwargs)

    def _get_pathname(self, name):
        if self.location:
            return safe_join(self.location, name)
        return clean_name(name)

    def _open(self, name, mode="rb"):
        if "w" in mode:
            raise ValueError("Vercel Blob storage does not support writing via _open. Use save() instead.")
        return VercelBlobFile(name, self)

    def _save(self, name, content):
        pathname = self._get_pathname(name)
        content_type = (
            getattr(content, "content_type", None)
            or mimetypes.guess_type(name)[0]
            or "application/octet-stream"
        )

        headers = {
            "x-api-version": "7",
            "content-type": "application/octet-stream",
            "x-content-type": content_type,
            "x-vercel-blob-access": self.default_acl,
            "x-add-random-suffix": "1" if self.add_random_suffix else "0",
        }
        if self.allow_overwrite:
            headers["x-allow-overwrite"] = "1"
        if self.cache_control_max_age is not None:
            headers["x-cache-control-max-age"] = str(self.cache_control_max_age)

        content.open()
        response = self._make_request(
            "PUT",
            f"{VERCEL_BLOB_API_URL}/{pathname}",
            headers=headers,
            data=content.read(),
        )
        content.close()
        response.raise_for_status()

        data = response.json()
        stored_pathname = data["pathname"]

        # Strip location prefix to return just the relative name
        if self.location and stored_pathname.startswith(self.location.rstrip("/") + "/"):
            stored_pathname = stored_pathname[len(self.location.rstrip("/")) + 1:]

        return clean_name(stored_pathname)

    def delete(self, name):
        file_url = self.url(name)
        response = self._make_request(
            "POST",
            f"{VERCEL_BLOB_API_URL}/delete",
            json={"urls": [file_url]},
            headers={"content-type": "application/json"},
        )
        response.raise_for_status()

    def exists(self, name):
        file_url = self.url(name)
        response = self._make_request(
            "GET",
            f"{VERCEL_BLOB_API_URL}/",
            params={"url": file_url},
        )
        return response.status_code == 200

    def url(self, name):
        if self.base_url:
            pathname = self._get_pathname(name)
            return f"{self.base_url.rstrip('/')}/{pathname}"
        # Fall back to head API to discover the URL
        response = self._make_request(
            "GET",
            f"{VERCEL_BLOB_API_URL}/",
            params={"url": self._get_pathname(name)},
        )
        response.raise_for_status()
        return response.json()["url"]

    def size(self, name):
        file_url = self.url(name)
        response = self._make_request(
            "GET",
            f"{VERCEL_BLOB_API_URL}/",
            params={"url": file_url},
        )
        response.raise_for_status()
        return response.json()["size"]

    def listdir(self, path):
        prefix = self._get_pathname(path) if path else self.location
        params = {"prefix": prefix, "mode": "folded"}
        response = self._make_request(
            "GET",
            f"{VERCEL_BLOB_API_URL}/",
            params=params,
        )
        response.raise_for_status()
        data = response.json()

        prefix_stripped = (prefix.rstrip("/") + "/") if prefix else ""

        directories = []
        for folder in data.get("folders", []):
            folder_name = folder.removeprefix(prefix_stripped).rstrip("/")
            if folder_name:
                directories.append(folder_name)

        files = []
        for blob in data.get("blobs", []):
            file_name = blob["pathname"].removeprefix(prefix_stripped)
            if file_name:
                files.append(file_name)

        return directories, files
