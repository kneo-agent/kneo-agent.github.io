"""
Cookbook — Object store tool against MinIO / on-prem S3-compatible
==================================================================
Pattern for letting an agent list / get / put objects in an
on-premise S3-compatible store (MinIO, Ceph, SeaweedFS, AWS S3 with
``endpoint_url`` set to a private endpoint).

Highlights:

- The tool exposes ``list``, ``get``, ``put`` as separate tools so
  the agent's tool schema is precise — vs a single tool that
  switches on an ``op`` argument, which models conflate.
- Object content is base64-encoded on read so binary blobs survive
  the JSON tool-result envelope. The recipe caps the size returned
  to keep huge objects out of the model's context.
- The bucket is **fixed at registry-time**, so a compromised model
  can't pivot to a sibling bucket containing other tenants' data.
- A ``SecretProvider`` resolves the credentials; nothing related to
  the access key appears in the tool surface visible to the model.

Run::

    python examples/cookbook/object_store_tool.py

In your application, replace ``_FakeS3`` with::

    import boto3
    s3 = boto3.client(
        "s3",
        endpoint_url="https://minio.internal.corp:9000",
        aws_access_key_id=secrets.get("s3_access_key"),
        aws_secret_access_key=secrets.get("s3_secret_key"),
        verify="/etc/ssl/corp/ca.pem",
    )

The handler bodies are unchanged — they use only ``s3.list_objects_v2``,
``s3.get_object``, ``s3.put_object``.
"""

import base64
import json
from dataclasses import dataclass, field
from typing import Any

from kneo_agent import ToolDefinition
from kneo_agent.utils import MappingSecretProvider, ToolRegistry

# ── 1. Offline S3-compatible mock so the recipe runs in CI ──────────


@dataclass
class _S3Object:
    body: bytes
    content_type: str = "application/octet-stream"


@dataclass
class _FakeS3:
    """Minimal stand-in for the boto3 ``s3`` client surface used here.

    Implements ``list_objects_v2``, ``get_object``, ``put_object``."""

    storage: dict[str, dict[str, _S3Object]] = field(default_factory=dict)

    def list_objects_v2(self, *, Bucket: str, Prefix: str = "", MaxKeys: int = 100):
        objs = sorted(
            k for k in self.storage.get(Bucket, {}) if k.startswith(Prefix)
        )[:MaxKeys]
        return {
            "Contents": [
                {"Key": k, "Size": len(self.storage[Bucket][k].body)} for k in objs
            ],
            "IsTruncated": False,
        }

    def get_object(self, *, Bucket: str, Key: str):
        obj = self.storage.get(Bucket, {}).get(Key)
        if obj is None:
            raise KeyError(f"NoSuchKey: {Bucket}/{Key}")

        class _Body:
            def __init__(self, data: bytes) -> None:
                self._data = data

            def read(self) -> bytes:
                return self._data

        return {"Body": _Body(obj.body), "ContentType": obj.content_type}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str = "application/octet-stream"):
        self.storage.setdefault(Bucket, {})[Key] = _S3Object(Body, ContentType)
        return {"ETag": f'"{hash(Body) & 0xFFFFFFFF:08x}"'}


# ── 2. Tool factory bound to (client, bucket) ───────────────────────


_MAX_GET_BYTES = 256 * 1024


def make_object_store_tools(s3: Any, bucket: str):
    def list_handler(args: dict[str, Any]) -> str:
        prefix = args.get("prefix", "")
        max_keys = min(int(args.get("max_keys", 100)), 1000)
        page = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=max_keys)
        return json.dumps({
            "objects": [{"key": o["Key"], "size": o["Size"]} for o in page.get("Contents", [])],
            "truncated": page.get("IsTruncated", False),
        })

    def get_handler(args: dict[str, Any]) -> str:
        key = args["key"]
        try:
            response = s3.get_object(Bucket=bucket, Key=key)
        except KeyError as exc:
            return json.dumps({"error": str(exc)})
        body = response["Body"].read()
        if len(body) > _MAX_GET_BYTES:
            return json.dumps({
                "error": "object too large",
                "size": len(body),
                "limit": _MAX_GET_BYTES,
            })
        return json.dumps({
            "key": key,
            "content_type": response.get("ContentType"),
            "size": len(body),
            "body_b64": base64.b64encode(body).decode("ascii"),
        })

    def put_handler(args: dict[str, Any]) -> str:
        key = args["key"]
        body = base64.b64decode(args["body_b64"])
        content_type = args.get("content_type", "application/octet-stream")
        result = s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType=content_type)
        return json.dumps({"key": key, "etag": result.get("ETag", "").strip('"')})

    return list_handler, get_handler, put_handler


# ── 3. Wire it ──────────────────────────────────────────────────────


def main() -> None:
    # In real use, pass these into boto3.client("s3", endpoint_url=...,
    # aws_access_key_id=secrets.get("s3_access_key"), ...). The fake
    # here ignores credentials, but the variable stays so the recipe
    # matches the production wiring shape.
    _secrets = MappingSecretProvider({
        "s3_access_key": "REDACTED-ACCESS-KEY",
        "s3_secret_key": "REDACTED-SECRET-KEY",
    })
    _ = _secrets
    # In your app:
    #     s3 = boto3.client("s3", endpoint_url="https://minio.internal.corp:9000", ...)
    s3 = _FakeS3({
        "documents": {
            "policy.txt": _S3Object(b"Be excellent.", "text/plain"),
            "report.pdf": _S3Object(b"%PDF-1.4 ...", "application/pdf"),
        }
    })
    list_h, get_h, put_h = make_object_store_tools(s3, bucket="documents")

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="objects_list",
            description="List objects in the bound bucket.",
            parameters={
                "type": "object",
                "properties": {
                    "prefix": {"type": "string"},
                    "max_keys": {"type": "integer"},
                },
                "required": [],
            },
        ),
        list_h,
    )
    registry.register(
        ToolDefinition(
            name="objects_get",
            description="Fetch an object by key. Returns base64 body.",
            parameters={
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
        ),
        get_h,
    )
    registry.register(
        ToolDefinition(
            name="objects_put",
            description="Write an object (base64-encoded body).",
            parameters={
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                    "body_b64": {"type": "string"},
                    "content_type": {"type": "string"},
                },
                "required": ["key", "body_b64"],
            },
        ),
        put_h,
    )

    print("list   :", list_h({"prefix": ""}))
    print("get    :", get_h({"key": "policy.txt"}))
    print("put    :", put_h({"key": "new.txt", "body_b64": base64.b64encode(b"hello").decode()}))
    print("404    :", get_h({"key": "missing"}))
    # Confirm secrets never appeared in any tool result.
    serialized = list_h({}) + get_h({"key": "policy.txt"})
    assert "REDACTED-ACCESS-KEY" not in serialized
    assert "REDACTED-SECRET-KEY" not in serialized


if __name__ == "__main__":
    main()
