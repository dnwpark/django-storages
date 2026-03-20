"""Tests for the Vercel Blob storage backend."""

from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from storages.backends.vercel_blob import VercelBlobException, VercelBlobFile, VercelBlobStorage
from tests.utils import NonSeekableContentFile

MOCK_TOKEN = "verbl_test_token"
MOCK_BASE_URL = "https://abc123.public.blob.vercel-storage.com"


def make_storage(**kwargs):
    defaults = {"token": MOCK_TOKEN, "base_url": MOCK_BASE_URL}
    defaults.update(kwargs)
    return VercelBlobStorage(**defaults)


class TestVercelBlobStorageInit(TestCase):
    def test_requires_token(self):
        with self.assertRaises(ImproperlyConfigured):
            VercelBlobStorage(token=None)

    def test_location_cannot_start_with_slash(self):
        with self.assertRaises(ImproperlyConfigured):
            make_storage(location="/media")

    def test_default_settings(self):
        storage = make_storage()
        self.assertFalse(storage.allow_overwrite)
        self.assertFalse(storage.add_random_suffix)
        self.assertIsNone(storage.cache_control_max_age)
        self.assertEqual(storage.location, "")

    @override_settings(VERCEL_BLOB_TOKEN="settings_token")
    def test_token_from_django_settings(self):
        storage = VercelBlobStorage(base_url=MOCK_BASE_URL)
        self.assertEqual(storage.token, "settings_token")

    def test_override_class_variable(self):
        class CustomStorage(VercelBlobStorage):
            location = "custom-prefix"

        storage = CustomStorage(token=MOCK_TOKEN, base_url=MOCK_BASE_URL)
        self.assertEqual(storage.location, "custom-prefix")

    def test_override_init_argument(self):
        storage = make_storage(location="init-prefix", allow_overwrite=True)
        self.assertEqual(storage.location, "init-prefix")
        self.assertTrue(storage.allow_overwrite)


class TestVercelBlobStorageUrl(TestCase):
    def test_url_with_base_url(self):
        storage = make_storage()
        self.assertEqual(storage.url("myfile.txt"), f"{MOCK_BASE_URL}/myfile.txt")

    def test_url_with_location(self):
        storage = make_storage(location="media")
        self.assertEqual(storage.url("photo.jpg"), f"{MOCK_BASE_URL}/media/photo.jpg")

    def test_url_base_url_trailing_slash_normalized(self):
        storage = make_storage(base_url=MOCK_BASE_URL + "/")
        self.assertEqual(storage.url("file.txt"), f"{MOCK_BASE_URL}/file.txt")

    def test_url_special_characters(self):
        storage = make_storage()
        url = storage.url("uploads/my file (1).jpg")
        self.assertIn("uploads/my file (1).jpg", url)

    @patch("storages.backends.vercel_blob.requests.request")
    def test_url_without_base_url_calls_head(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"url": f"{MOCK_BASE_URL}/file.txt"}
        mock_request.return_value = mock_response

        storage = make_storage(base_url=None)
        url = storage.url("file.txt")
        self.assertEqual(url, f"{MOCK_BASE_URL}/file.txt")


class TestVercelBlobStorageSave(TestCase):
    @patch("storages.backends.vercel_blob.requests.request")
    def test_save_basic(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "url": f"{MOCK_BASE_URL}/hello.txt",
            "pathname": "hello.txt",
        }
        mock_request.return_value = mock_response

        storage = make_storage()
        name = storage._save("hello.txt", ContentFile(b"hello world"))
        self.assertEqual(name, "hello.txt")

        call_kwargs = mock_request.call_args
        self.assertEqual(call_kwargs[0][0], "PUT")
        self.assertIn("hello.txt", call_kwargs[0][1])

    @patch("storages.backends.vercel_blob.requests.request")
    def test_save_with_location_strips_prefix(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "url": f"{MOCK_BASE_URL}/media/photo.jpg",
            "pathname": "media/photo.jpg",
        }
        mock_request.return_value = mock_response

        storage = make_storage(location="media")
        name = storage._save("photo.jpg", ContentFile(b"img data"))
        self.assertEqual(name, "photo.jpg")

    @patch("storages.backends.vercel_blob.requests.request")
    def test_save_sends_access_header(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"url": f"{MOCK_BASE_URL}/f.txt", "pathname": "f.txt"}
        mock_request.return_value = mock_response

        storage = make_storage(default_acl="private")
        storage._save("f.txt", ContentFile(b"data"))
        headers = mock_request.call_args[1]["headers"]
        self.assertEqual(headers["x-vercel-blob-access"], "private")

    @patch("storages.backends.vercel_blob.requests.request")
    def test_save_sets_content_type(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"url": f"{MOCK_BASE_URL}/img.png", "pathname": "img.png"}
        mock_request.return_value = mock_response

        storage = make_storage()
        storage._save("img.png", ContentFile(b"\x89PNG"))

        headers = mock_request.call_args[1]["headers"]
        self.assertEqual(headers["x-content-type"], "image/png")

    @patch("storages.backends.vercel_blob.requests.request")
    def test_save_content_type_from_file_object(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"url": f"{MOCK_BASE_URL}/upload", "pathname": "upload"}
        mock_request.return_value = mock_response

        content = ContentFile(b"data")
        content.content_type = "image/webp"

        storage = make_storage()
        storage._save("upload", content)

        headers = mock_request.call_args[1]["headers"]
        self.assertEqual(headers["x-content-type"], "image/webp")

    @patch("storages.backends.vercel_blob.requests.request")
    def test_save_with_cache_control(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"url": f"{MOCK_BASE_URL}/f.txt", "pathname": "f.txt"}
        mock_request.return_value = mock_response

        storage = make_storage(cache_control_max_age=3600)
        storage._save("f.txt", ContentFile(b"data"))

        headers = mock_request.call_args[1]["headers"]
        self.assertEqual(headers["x-cache-control-max-age"], "3600")


    @patch("storages.backends.vercel_blob.requests.request")
    def test_save_add_random_suffix_returns_actual_name(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "url": f"{MOCK_BASE_URL}/hello-abc123.txt",
            "pathname": "hello-abc123.txt",
        }
        mock_request.return_value = mock_response

        storage = make_storage(add_random_suffix=True)
        name = storage._save("hello.txt", ContentFile(b"data"))
        self.assertEqual(name, "hello-abc123.txt")

    @patch("storages.backends.vercel_blob.requests.request")
    def test_save_non_seekable_content(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"url": f"{MOCK_BASE_URL}/f.txt", "pathname": "f.txt"}
        mock_request.return_value = mock_response

        storage = make_storage()
        storage._save("f.txt", NonSeekableContentFile(b"data"))
        self.assertTrue(mock_request.called)

    @patch("storages.backends.vercel_blob.requests.request")
    def test_save_unknown_content_type_defaults_to_octet_stream(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"url": f"{MOCK_BASE_URL}/f.bin", "pathname": "f.bin"}
        mock_request.return_value = mock_response

        storage = make_storage()
        storage._save("f.unknownextension", ContentFile(b"data"))

        headers = mock_request.call_args[1]["headers"]
        self.assertEqual(headers["x-content-type"], "application/octet-stream")


class TestVercelBlobStorageDelete(TestCase):
    @patch("storages.backends.vercel_blob.requests.request")
    def test_delete(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        storage = make_storage()
        storage.delete("myfile.txt")

        call_args = mock_request.call_args
        self.assertEqual(call_args[0][0], "POST")
        self.assertIn("delete", call_args[0][1])
        self.assertIn(f"{MOCK_BASE_URL}/myfile.txt", call_args[1]["json"]["urls"])


class TestVercelBlobStorageExists(TestCase):
    @patch("storages.backends.vercel_blob.requests.request")
    def test_exists_true(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"blobs": [{"pathname": "file.txt"}]}
        mock_request.return_value = mock_response

        storage = make_storage()
        self.assertTrue(storage.exists("file.txt"))

    @patch("storages.backends.vercel_blob.requests.request")
    def test_exists_false_empty_list(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"blobs": []}
        mock_request.return_value = mock_response

        storage = make_storage()
        self.assertFalse(storage.exists("missing.txt"))

    @patch("storages.backends.vercel_blob.requests.request")
    def test_exists_false_on_error(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_request.return_value = mock_response

        storage = make_storage()
        self.assertFalse(storage.exists("file.txt"))

    @patch("storages.backends.vercel_blob.requests.request")
    def test_exists_no_base_url(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"blobs": [{"pathname": "file.txt"}]}
        mock_request.return_value = mock_response

        storage = make_storage(base_url=None)
        self.assertTrue(storage.exists("file.txt"))


class TestVercelBlobStorageSize(TestCase):
    @patch("storages.backends.vercel_blob.requests.request")
    def test_size(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"size": 1024, "url": f"{MOCK_BASE_URL}/f.txt"}
        mock_request.return_value = mock_response

        storage = make_storage()
        self.assertEqual(storage.size("f.txt"), 1024)


class TestVercelBlobStorageListdir(TestCase):
    @patch("storages.backends.vercel_blob.requests.request")
    def test_listdir(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "blobs": [
                {"pathname": "media/file1.txt"},
                {"pathname": "media/file2.jpg"},
            ],
            "folders": ["media/subfolder/"],
        }
        mock_request.return_value = mock_response

        storage = make_storage(location="media")
        dirs, files = storage.listdir("")
        self.assertEqual(dirs, ["subfolder"])
        self.assertEqual(files, ["file1.txt", "file2.jpg"])


class TestVercelBlobFile(TestCase):
    @patch("storages.backends.vercel_blob.requests.request")
    def test_open_and_read(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"file content"
        mock_request.return_value = mock_response

        storage = make_storage()
        f = storage._open("file.txt")
        self.assertIsInstance(f, VercelBlobFile)
        self.assertEqual(f.read(), b"file content")

    def test_open_write_mode_raises(self):
        storage = make_storage()
        with self.assertRaises(ValueError):
            storage._open("file.txt", mode="wb")
