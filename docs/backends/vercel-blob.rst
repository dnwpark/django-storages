Vercel Blob
===========

A storage backend for `Vercel Blob`_.

.. _Vercel Blob: https://vercel.com/docs/storage/vercel-blob

Installation
------------

Install with the ``vercel`` extra::

    pip install django-storages[vercel]

Configuration & Settings
------------------------

To use Vercel Blob as the default file storage backend::

  STORAGES = {
      "default": {
          "BACKEND": "storages.backends.vercel_blob.VercelBlobStorage",
          "OPTIONS": {
            ...your_options_here
          },
      },
  }

The settings below list both the ``OPTIONS`` key and the equivalent Django
setting. See the `Vercel Blob SDK reference`_ for further details on each
option.

.. _Vercel Blob SDK reference: https://vercel.com/docs/vercel-blob/using-blob-sdk

Credentials
~~~~~~~~~~~

Vercel sets ``BLOB_READ_WRITE_TOKEN`` automatically in deployed environments.
For local development, copy it from the Vercel dashboard under
**Storage → your store → Settings**.

``token`` or ``VERCEL_BLOB_TOKEN``

  **Required.** Your Vercel Blob read-write token.

Settings
~~~~~~~~

``base_url`` or ``VERCEL_BLOB_BASE_URL``

  **Strongly recommended.** The root URL of your blob store, e.g.
  ``https://abc123.public.blob.vercel-storage.com``. When set, ``url()``
  constructs file URLs locally without making an API call. If omitted, each
  ``url()`` call issues an HTTP request to the Vercel Blob API.

  Find your store URL in the Vercel dashboard under **Storage → your store**.

``location`` or ``VERCEL_BLOB_LOCATION``

  Default: ``""``

  A path prefix prepended to all stored file names, e.g. ``"media"`` or
  ``"uploads"``.

``access`` or ``VERCEL_BLOB_ACCESS``

  Default: ``"public"``

  Access level for uploaded files: ``"public"`` or ``"private"``. Public stores
  accept either value; private stores only accept ``"private"``.

``allow_overwrite`` or ``VERCEL_BLOB_ALLOW_OVERWRITE``

  Default: ``False``

  When ``True``, saving a file with an existing pathname replaces it in the
  store. Note that CDN caches may take up to 60 seconds to reflect the change.

``add_random_suffix`` or ``VERCEL_BLOB_ADD_RANDOM_SUFFIX``

  Default: ``False``

  When ``True``, Vercel appends a random suffix to the stored pathname to
  guarantee uniqueness. The actual stored name is recorded in the model field.

``cache_control_max_age`` or ``VERCEL_BLOB_CACHE_CONTROL_MAX_AGE``

  Default: ``None``

  Override the CDN cache TTL (in seconds) for uploaded files. When ``None``,
  Vercel uses its default (typically 1 year for public blobs).

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
  the bearer token.
