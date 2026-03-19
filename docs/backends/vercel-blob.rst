Vercel Blob
===========

A storage backend for `Vercel Blob`_.

.. _Vercel Blob: https://vercel.com/docs/storage/vercel-blob

Installation
------------

Install with the ``vercel`` extra::

    pip install django-storages[vercel]

Settings
--------

All settings are available in the Vercel dashboard under **Storage → your store**.
Vercel sets ``BLOB_READ_WRITE_TOKEN`` automatically in deployed environments; for
local development, copy it from the store's settings page.

``VERCEL_BLOB_TOKEN``

  **Required.** Your Vercel Blob read-write token.

``VERCEL_BLOB_BASE_URL``

  **Strongly recommended.** The root URL of your blob store, e.g.
  ``https://abc123.public.blob.vercel-storage.com``. When set, ``url()`` constructs
  file URLs locally without making an API call. If omitted, each ``url()`` call issues
  an HTTP request to the Vercel Blob API.

``VERCEL_BLOB_LOCATION``

  Default: ``""``

  A path prefix prepended to all stored file names, e.g. ``"media"`` or ``"uploads"``.

``VERCEL_BLOB_DEFAULT_ACL``

  Default: ``"public"``

  Access level for uploaded files. Must match your store's access configuration in
  the Vercel dashboard. Set to ``"private"`` for private stores.

``VERCEL_BLOB_ALLOW_OVERWRITE``

  Default: ``False``

  When ``True``, saving a file with an existing pathname replaces it in the store.
  Note that CDN caches may take up to 60 seconds to reflect the change.

``VERCEL_BLOB_ADD_RANDOM_SUFFIX``

  Default: ``False``

  When ``True``, Vercel appends a random suffix to the stored pathname to guarantee
  uniqueness. The actual stored name is recorded in the model field.

``VERCEL_BLOB_CACHE_CONTROL_MAX_AGE``

  Default: ``None``

  Override the CDN cache TTL (in seconds) for uploaded files. When ``None``, Vercel
  uses its default (typically 1 year for public blobs).

Configuration
-------------

Add the following to your Django settings:

.. code-block:: python

    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.vercel_blob.VercelBlobStorage",
            "OPTIONS": {
                "token": "verbl_...",        # or omit and set VERCEL_BLOB_TOKEN
                "base_url": "https://<store-id>.public.blob.vercel-storage.com",
                "location": "media",
            },
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

Notes
-----

- Vercel Blob does not support directories. Folders are simulated via ``/`` in
  pathnames. ``listdir()`` uses Vercel's folded listing mode to present this as a
  directory tree.
- Write-mode file opening (``open(name, "wb")``) is not supported. Use
  ``storage.save()`` to upload files.
- Deleting a file that does not exist is a no-op (idempotent).
- For **private** blobs, ``url()`` returns the raw blob URL which requires
  authentication. You will need to proxy downloads through a Django view that adds
  the bearer token. Public blob stores are recommended for use with Django's
  ``ImageField`` and ``FileField``.
