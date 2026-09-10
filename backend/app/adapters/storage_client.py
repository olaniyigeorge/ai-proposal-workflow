"""
The only module allowed to import the Supabase Storage SDK directly (per
CLAUDE.md: "adapters are the only place that import a third-party SDK").
"""

from supabase import AsyncClient, acreate_client

from app.core.config import settings


class StorageUploadError(Exception):
    """Raised on any failure uploading to or reading from Supabase Storage."""


_client: AsyncClient | None = None


async def _get_client() -> AsyncClient:
    global _client
    if _client is None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
            raise StorageUploadError(
                "SUPABASE_URL/SUPABASE_KEY are not configured — cannot reach Storage"
            )
        _client = await acreate_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    return _client


async def upload_pdf(path: str, pdf_bytes: bytes) -> None:
    """Uploads (or overwrites) a PDF at `path` within DOCUMENT_STORAGE_BUCKET.
    `upsert` is safe here because the caller (document_service.py) only ever
    calls this once per proposal — the DB unique constraint on
    DocumentArtifact.proposal_id is what actually enforces "generated exactly
    once", this is not a retry-friendly overwrite path by design.
    """
    client = await _get_client()
    try:
        await client.storage.from_(settings.DOCUMENT_STORAGE_BUCKET).upload(
            path,
            pdf_bytes,
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )
    except Exception as exc:
        raise StorageUploadError(f"Failed to upload document: {exc}") from exc


async def get_signed_url(path: str, expires_in_seconds: int = 3600) -> str:
    """Signed URLs are generated on demand, never stored — so a bucket
    policy change or key rotation doesn't require touching every existing
    DocumentArtifact row.
    """
    client = await _get_client()
    try:
        result = await client.storage.from_(settings.DOCUMENT_STORAGE_BUCKET).create_signed_url(
            path, expires_in_seconds
        )
    except Exception as exc:
        raise StorageUploadError(f"Failed to create signed URL: {exc}") from exc

    signed_url = result.get("signedURL") or result.get("signedUrl")
    if not signed_url:
        raise StorageUploadError(f"Storage did not return a signed URL: {result}")
    return signed_url
