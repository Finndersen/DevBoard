"""Initiative database model."""

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .document import Document
    from .project import Project
    from .task import Task


class Initiative(Base):
    """Represents a scoped initiative within a project.

    Initiatives are managed from within the parent project by the project agent.
    They have their own context document and can contain tasks.
    """

    __tablename__ = "initiatives"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(300))
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    specification_document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    complete: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))

    project: Mapped["Project"] = relationship(back_populates="initiatives")
    specification: Mapped["Document"] = relationship(
        foreign_keys=[specification_document_id],
        lazy="joined",
        cascade="all, delete-orphan",
        single_parent=True,
    )
    tasks: Mapped[list["Task"]] = relationship(back_populates="initiative")
