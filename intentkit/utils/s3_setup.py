import json
import logging

from botocore.exceptions import ClientError

from intentkit.clients.s3 import get_s3_client
from intentkit.config.config import config

logger = logging.getLogger(__name__)


def ensure_bucket_exists_and_public() -> None:
    """
    Ensure the configured S3 bucket exists and has a public read policy.
    This is primarily for RustFS integration.
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
        # 1. Check if bucket exists
        try:
            client.head_bucket(Bucket=bucket_name)
            logger.info(f"Bucket '{bucket_name}' already exists.")
            # If bucket exists, we assume it's already configured correctly.
            # We do NOT attempt to set the policy to avoid overwriting existing configurations
            # or triggering errors on providers that don't support it (like Supabase S3).
            return
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "404":
                # Bucket does not exist, create it
                logger.info(f"Bucket '{bucket_name}' not found. Creating it...")
                client.create_bucket(Bucket=bucket_name)
                logger.info(f"Bucket '{bucket_name}' created successfully.")

                # 2. Set public read policy ONLY if we created the bucket
                # This policy allows public read access to all objects in the bucket
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

                # Convert policy to JSON string
                policy_json = json.dumps(policy)

                logger.info(f"Setting public read policy for bucket '{bucket_name}'...")
                try:
                    client.put_bucket_policy(Bucket=bucket_name, Policy=policy_json)
                    logger.info(f"Public read policy set for bucket '{bucket_name}'.")
                except ClientError as pe:
                    # Log but don't fail if policy setting fails
                    logger.warning(f"Failed to set bucket policy: {pe}")

            else:
                # Other error, re-raise
                logger.error(f"Failed to check bucket existence: {e}")
                raise

    except Exception as e:
        logger.error(f"Failed to ensure bucket exists and is public: {e}")
        # We don't want to crash the app if S3 setup fails, just log the error
