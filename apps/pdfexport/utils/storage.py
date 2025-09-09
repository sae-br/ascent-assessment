import io
import boto3
from botocore.client import Config
from urllib.parse import quote as urlquote

class S3Uploader:
    def __init__(self, bucket, region, access_key, secret_key):
        self.bucket = bucket
        self.region = region
        self.session = boto3.session.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        self.client = self.session.client("s3", config=Config(signature_version="s3v4"))

        # Small helper: RFC 5987/6266 compatible disposition (ASCII fallback + UTF-8 filename*)
        self._disposition = lambda pretty: (
            f'attachment; filename="{self._ascii_fallback(pretty)}"; '
            f"filename*=UTF-8''{urlquote(pretty)}"
        )

    @staticmethod
    def _ascii_fallback(name: str) -> str:
        try:
            name.encode("ascii")
            return name  # already ascii
        except UnicodeEncodeError:
            # conservative fallback: replace non-ascii with '_'
            return "".join(ch if ord(ch) < 128 else "_" for ch in name)

    def upload_bytes(self, data: bytes, key: str, content_type: str = "application/octet-stream"):
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=io.BytesIO(data),
            ContentType=content_type,
            ACL="private",
        )
        return key, len(data)

    def upload_file(self, local_path: str, key: str, content_type: str = "application/octet-stream"):
        extra = {"ContentType": content_type, "ACL": "private"}
        self.client.upload_file(local_path, self.bucket, key, ExtraArgs=extra)
        import os
        size = os.path.getsize(local_path)
        return key, size

    def presign_get(
        self,
        key: str,
        expires_seconds: int = 300,
        *,
        pretty_filename: str | None = None,
        content_type: str | None = None,
    ) -> str:
        params = {"Bucket": self.bucket, "Key": key}
        if pretty_filename:
            params["ResponseContentDisposition"] = self._disposition(pretty_filename)
        if content_type:
            params["ResponseContentType"] = content_type

        return self.client.generate_presigned_url(
            ClientMethod="get_object",
            Params=params,
            ExpiresIn=expires_seconds,
        )