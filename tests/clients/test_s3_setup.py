"""Tests for S3 bucket setup startup behavior."""

from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError, EndpointConnectionError

from intentkit.clients.s3_setup import ensure_bucket_exists_and_public
from intentkit.utils import readiness


def _run_with(client: MagicMock) -> None:
    with (
        patch("intentkit.clients.s3_setup.get_s3_client", return_value=client),
        patch("intentkit.clients.s3_setup.config") as cfg,
    ):
        cfg.aws_s3_endpoint_url = "http://rustfs:9000"
        cfg.aws_s3_bucket = "bucket"
        ensure_bucket_exists_and_public()


def test_retries_connection_errors_until_store_is_up(monkeypatch):
    client = MagicMock()
    client.head_bucket.side_effect = [
        EndpointConnectionError(endpoint_url="http://rustfs:9000"),
        {},
    ]
    monkeypatch.setattr(readiness, "READY_INTERVAL", 0)

    _run_with(client)

    assert client.head_bucket.call_count == 2
    client.create_bucket.assert_not_called()


def test_retries_server_errors_while_store_boots(monkeypatch):
    client = MagicMock()
    client.head_bucket.side_effect = [
        ClientError(
            {
                "Error": {"Code": "503", "Message": "Service Unavailable"},
                "ResponseMetadata": {"HTTPStatusCode": 503},
            },
            "HeadBucket",
        ),
        {},
    ]
    monkeypatch.setattr(readiness, "READY_INTERVAL", 0)

    _run_with(client)

    assert client.head_bucket.call_count == 2
    client.create_bucket.assert_not_called()


def test_missing_bucket_is_created_with_public_policy():
    client = MagicMock()
    client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "404"}}, "HeadBucket"
    )

    _run_with(client)

    client.create_bucket.assert_called_once_with(Bucket="bucket")
    client.put_bucket_policy.assert_called_once()


def test_create_race_lost_to_concurrent_service():
    client = MagicMock()
    client.head_bucket.side_effect = ClientError(
        {"Error": {"Code": "404"}}, "HeadBucket"
    )
    client.create_bucket.side_effect = ClientError(
        {"Error": {"Code": "BucketAlreadyOwnedByYou"}}, "CreateBucket"
    )

    _run_with(client)

    # The winner of the race sets the policy; the loser must not.
    client.put_bucket_policy.assert_not_called()
