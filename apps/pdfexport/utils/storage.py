import io
import boto3
from botocore.client import Config

class S3Uploader:
    def __init__(self, bucket, region, access_key, secret_key):
        self.bucket = bucket
        self.region = region
        self.session = boto3.session.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        # accelerate off by default; signature v4
        self.client = self.session.client("s3", config=Config(signature_version="s3v4"))

    def upload_bytes(self, data: bytes, key: str, content_type: str = "application/octet-stream"):
        """Upload in-memory bytes to S3."""
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=io.BytesIO(data),
            ContentType=content_type,
            ACL="private",
        )
        return key, len(data)

    def upload_file(self, local_path: str, key: str, content_type: str = "application/octet-stream"):
        """Upload a local file path to S3."""
        extra = {"ContentType": content_type, "ACL": "private"}
        self.client.upload_file(local_path, self.bucket, key, ExtraArgs=extra)
        # we don’t know size without stat; do it if you care:
        import os
        size = os.path.getsize(local_path)
        return key, size

    def presign_get(self, key: str, expires_seconds: int = 300) -> str:
        """Generate a time-limited HTTPS URL for downloading the object."""
        return self.client.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_seconds,
        )