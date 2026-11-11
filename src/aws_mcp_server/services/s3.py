"""Amazon S3 tools."""

import boto3
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from ..config import Settings
from ..utils import jsonable
from .base import BaseService


class S3Service(BaseService):
    def __init__(self, settings: Settings, session: boto3.Session) -> None:
        super().__init__(settings, session)
        self.client = session.client("s3")

    def _bucket(self, bucket: str | None) -> str:
        name = bucket or self.settings.s3_default_bucket
        if not name:
            raise ToolError("No bucket given and S3_DEFAULT_BUCKET is not set.")
        return name

    def register(self, mcp: FastMCP) -> None:
        for function in (
            self.s3_list_buckets,
            self.s3_list_objects,
            self.s3_head_object,
            self.s3_read_object,
            self.s3_generate_presigned_url,
            self.s3_put_object,
            self.s3_delete_object,
        ):
            mcp.tool(function)

    async def s3_list_buckets(self) -> list[dict]:
        """List all S3 buckets visible to the configured AWS credentials."""
        response = await self._run(self.client.list_buckets)
        buckets = [
            {"name": bucket["Name"], "created": bucket["CreationDate"]}
            for bucket in response["Buckets"]
        ]
        return jsonable(buckets)

    async def s3_list_objects(
        self,
        bucket: str | None = None,
        prefix: str = "",
        max_keys: int = 100,
        continuation_token: str | None = None,
    ) -> dict:
        """List one page of objects and return a token when more results exist."""
        bucket_name = self._bucket(bucket)
        params = {
            "Bucket": bucket_name,
            "Prefix": prefix,
            "MaxKeys": max(1, min(max_keys, 1000)),
        }
        if continuation_token:
            params["ContinuationToken"] = continuation_token

        response = await self._run(self.client.list_objects_v2, **params)
        objects = [
            {
                "key": item["Key"],
                "size": item["Size"],
                "last_modified": item["LastModified"],
                "storage_class": item.get("StorageClass"),
            }
            for item in response.get("Contents", [])
        ]
        return jsonable(
            {
                "bucket": bucket_name,
                "prefix": prefix,
                "truncated": response.get("IsTruncated", False),
                "next_continuation_token": response.get("NextContinuationToken"),
                "objects": objects,
            }
        )

    async def s3_head_object(self, key: str, bucket: str | None = None) -> dict:
        """Get metadata for an object."""
        bucket_name = self._bucket(bucket)
        response = await self._run(
            self.client.head_object,
            Bucket=bucket_name,
            Key=key,
        )
        return jsonable(
            {
                "bucket": bucket_name,
                "key": key,
                "size": response["ContentLength"],
                "content_type": response.get("ContentType"),
                "etag": response.get("ETag"),
                "last_modified": response.get("LastModified"),
                "metadata": response.get("Metadata", {}),
            }
        )

    async def s3_read_object(self, key: str, bucket: str | None = None) -> dict:
        """Read a UTF-8 object up to S3_MAX_READ_BYTES."""
        bucket_name = self._bucket(bucket)
        limit = self.settings.s3_max_read_bytes

        def read_object() -> dict:
            response = self.client.get_object(
                Bucket=bucket_name,
                Key=key,
                Range=f"bytes=0-{limit - 1}",
            )
            body = response["Body"].read()
            total_size = response.get("ContentRange", "").split("/")[-1]
            total = int(total_size) if total_size.isdigit() else len(body)
            return {
                "bucket": bucket_name,
                "key": key,
                "content_type": response.get("ContentType"),
                "bytes_returned": len(body),
                "total_size": total,
                "truncated": total > len(body),
                "content": body.decode("utf-8", errors="replace"),
            }

        return await self._run(read_object)

    async def s3_generate_presigned_url(
        self,
        key: str,
        bucket: str | None = None,
        expires_in: int = 900,
        method: str = "get_object",
    ) -> dict:
        """Create a presigned GET or PUT URL. PUT requires ALLOW_WRITES=true."""
        if method not in {"get_object", "put_object"}:
            raise ToolError("method must be 'get_object' or 'put_object'.")
        if method == "put_object":
            self._require_writes("s3_generate_presigned_url(put_object)")

        bucket_name = self._bucket(bucket)
        ttl = max(60, min(expires_in, 7 * 24 * 3600))
        url = await self._run(
            self.client.generate_presigned_url,
            ClientMethod=method,
            Params={"Bucket": bucket_name, "Key": key},
            ExpiresIn=ttl,
        )
        return {"url": url, "method": method, "expires_in": ttl}

    async def s3_put_object(
        self,
        key: str,
        content: str,
        bucket: str | None = None,
        content_type: str = "text/plain; charset=utf-8",
    ) -> dict:
        """Write a UTF-8 text object. Requires ALLOW_WRITES=true."""
        self._require_writes("s3_put_object")
        bucket_name = self._bucket(bucket)
        response = await self._run(
            self.client.put_object,
            Bucket=bucket_name,
            Key=key,
            Body=content.encode("utf-8"),
            ContentType=content_type,
        )
        return {"bucket": bucket_name, "key": key, "etag": response.get("ETag")}

    async def s3_delete_object(self, key: str, bucket: str | None = None) -> dict:
        """Delete an S3 object. Requires ALLOW_WRITES=true."""
        self._require_writes("s3_delete_object")
        bucket_name = self._bucket(bucket)
        await self._run(self.client.delete_object, Bucket=bucket_name, Key=key)
        return {"bucket": bucket_name, "key": key, "deleted": True}