import uuid
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class DocumentArtifact(Base, TimestampMixin):
    """The one branded PDF generated for a Proposal — exactly once, at
    APPROVED (CLAUDE.md: "The PDF is generated exactly once... there is no
    'draft PDF'"). `unique=True` on proposal_id is the DB-level backstop for
    that rule; the application-level guard lives in
    services/document_service.py.
    """

    __tablename__ = "document_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4, nullable=False
    )
    proposal_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("proposals.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    # Bucket-relative key (DOCUMENT_STORAGE_BUCKET) — not a URL. Download
    # links are signed on demand (adapters/storage_client.py) rather than
    # stored, so a bucket policy/key change never requires a data migration.
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[int] = mapped_column(Integer, nullable=False)

    proposal = relationship("Proposal")
