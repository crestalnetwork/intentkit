import json
import logging

from botocore.exceptions import ClientError, ConnectionClosedError, ReadTimeoutError
from botocore.exceptions import ConnectionError as BotoConnectionError
from mypy_boto3_s3.client import S3Client

from intentkit.clients.s3 import get_s3_client
from intentkit.config.config import config
from intentkit.utils.readiness import wait_until_ready_sync

logger = logging.getLogger(__name__)


class _S3NotReadyError(Exception):
    """Server-side 5xx during boot, translated so the wait loop retries it."""


def _probe_bucket(client: S3Client, bucket_name: str) -> None:
    try:
        _ = client.head_bucket(Bucket=bucket_name)
    except ClientError as e:
        status = e.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if isinstance(status, int) and status >= 500:
            raise _S3NotReadyError(str(e)) from e
        raise


def _create_public_bucket(client: S3Client, bucket_name: str) -> None:
    """Create the bucket and set a public read policy on it."""
    logger.info("Bucket '%s' not found. Creating it...", bucket_name)
    try:
        _ = client.create_bucket(Bucket=bucket_name)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code in ("BucketAlreadyOwnedByYou", "BucketAlreadyExists"):
            # Another service booting concurrently won the create race; the
            # winner sets the policy.
            logger.info("Bucket '%s' was just created by another service.", bucket_name)
            return
        raise
    logger.info("Bucket '%s' created successfully.", bucket_name)

    # Set public read policy ONLY if we created the bucket.
    # This policy allows public read access to all objects in the bucket.
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "PublicReadGetObject",
                "Effect": "Allow",
                "Principal": "*",
                "Action": ["s3:GetObject"],
                "Resource": [f"arn:aws:s3:::{bucket_name}/*"],
            }
        ],
    }

    logger.info("Setting public read policy for bucket '%s'...", bucket_name)
    try:
        _ = client.put_bucket_policy(Bucket=bucket_name, Policy=json.dumps(policy))
        logger.info("Public read policy set for bucket '%s'.", bucket_name)
    except ClientError as pe:
        # Log but don't fail if policy setting fails
        logger.warning("Failed to set bucket policy: %s", pe)


def ensure_bucket_exists_and_public() -> None:
    """
    Ensure the configured S3 bucket exists and has a public read policy.
    This is primarily for RustFS integration.

    Blocking, and may sleep while waiting for the object store to come up;
    call via ``asyncio.to_thread`` from async code.
    """
    # Only run if we have a bucket configured and we are in an appropriate env
    # For now, we assume this is safe to run if S3 is configured.
    # We only run this if a custom endpoint is configured (RustFS/MinIO)
    if not config.aws_s3_endpoint_url:
        return

    client = get_s3_client()
    if not client or not config.aws_s3_bucket:
        logger.warning(
            "S3 client not initialized or bucket not configured. Skipping bucket setup."
        )
        return

    bucket_name = config.aws_s3_bucket

    try:
        # Check if the bucket exists. Services restart in arbitrary order, so
        # the object store (RustFS/MinIO) may still be booting; retry
        # connection failures instead of alerting immediately.
        try:
            wait_until_ready_sync(
                "S3",
                lambda: _probe_bucket(client, bucket_name),
                (
                    BotoConnectionError,
                    ConnectionClosedError,
                    ReadTimeoutError,
                    _S3NotReadyError,
                ),
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code != "404":
                logger.error("Failed to check bucket existence: %s", e)
                raise
            _create_public_bucket(client, bucket_name)
        else:
            # If the bucket exists, we assume it's already configured
            # correctly. We do NOT attempt to set the policy to avoid
            # overwriting existing configurations or triggering errors on
            # providers that don't support it (like Supabase S3).
            logger.info("Bucket '%s' already exists.", bucket_name)
    except Exception:
        logger.exception("Failed to ensure bucket exists and is public")
        # We don't want to crash the app if S3 setup fails, just log the error
