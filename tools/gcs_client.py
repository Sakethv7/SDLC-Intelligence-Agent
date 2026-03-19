"""Google Cloud Storage client for uploading Insight Agent reports.

Requires:
  - google-cloud-storage in requirements.txt
  - GCS_BUCKET env var set to target bucket name
  - GCP_PROJECT_ID env var (used when creating bucket if it doesn't exist)
  - Standard GCP credentials: GOOGLE_APPLICATION_CREDENTIALS or Workload Identity

Reports are uploaded to: gs://<GCS_BUCKET>/pipeline-reports/<pipeline_id>.html
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_client = None
_bucket = None


def _get_bucket():
    global _client, _bucket
    if _bucket is not None:
        return _bucket

    try:
        from google.cloud import storage  # type: ignore
    except ImportError:
        logger.warning("google-cloud-storage not installed; GCS upload skipped")
        return None

    bucket_name = os.environ.get("GCS_BUCKET", "").strip()
    if not bucket_name:
        return None

    _client = storage.Client(project=os.environ.get("GCP_PROJECT_ID"))
    _bucket = _client.bucket(bucket_name)
    return _bucket


def upload_report(pipeline_id: int | str, html_content: str) -> str | None:
    """Upload an HTML report to GCS. Returns the public URL or None if skipped."""
    bucket = _get_bucket()
    if bucket is None:
        return None

    blob_name = f"pipeline-reports/{pipeline_id}.html"
    blob = bucket.blob(blob_name)
    blob.upload_from_string(html_content, content_type="text/html")
    bucket_name = os.environ.get("GCS_BUCKET", "")
    url = f"https://storage.googleapis.com/{bucket_name}/{blob_name}"
    logger.info("Uploaded pipeline report to %s", url)
    return url


def upload_file(local_path: str | Path, destination: str) -> str | None:
    """Upload any local file to GCS. Returns the public URL or None if skipped."""
    bucket = _get_bucket()
    if bucket is None:
        return None

    blob = bucket.blob(destination)
    blob.upload_from_filename(str(local_path))
    bucket_name = os.environ.get("GCS_BUCKET", "")
    url = f"https://storage.googleapis.com/{bucket_name}/{destination}"
    logger.info("Uploaded %s to %s", local_path, url)
    return url
