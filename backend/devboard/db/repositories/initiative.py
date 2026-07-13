"""Initiative repository for initiative data access operations."""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from devboard.db.models.document import Document
from devboard.db.models.initiative import Initiative
from devboard.db.repositories.base import BaseRepository


class InitiativeRepository(BaseRepository[Initiative]):
    """Repository for initiative data access operations."""

    def __init__(self, db_session: Session):
        super().__init__(db_session)

    def get_by_id(self, initiative_id: int) -> Initiative | None:
        """Get an initiative by its ID with specification eager-loaded."""
        stmt = select(Initiative).where(Initiative.id == initiative_id).options(joinedload(Initiative.specification))
        return self.db.execute(stmt).unique().scalar_one_or_none()

    def get_all(self, project_id: int, complete: bool | None = None) -> list[Initiative]:
        """Get initiatives for a project with optional completion filter.

        Args:
            project_id: Filter to initiatives belonging to this project.
            complete: Filter by completion status. None (default) excludes complete initiatives.
        """
        stmt = select(Initiative).where(Initiative.project_id == project_id)
        filter_complete = complete if complete is not None else False
        stmt = stmt.where(Initiative.complete == filter_complete)
        return list(self.db.execute(stmt).unique().scalars().all())

    def create(
        self,
        name: str,
        description: str,
        specification: "Document",
        project_id: int,
    ) -> Initiative:
        """Create a new initiative.

        Args:
            name: Initiative name
            description: Initiative description
            specification: Context document instance
            project_id: Parent project ID

        Returns:
            Created initiative with assigned ID
        """
        initiative = Initiative(
            name=name,
            description=description,
            specification_document_id=specification.id,
            project_id=project_id,
        )
        self.db.add(initiative)
        self.db.flush()
        return initiative

    def update(self, initiative: Initiative) -> Initiative:
        """Update an existing initiative."""
        self.db.merge(initiative)
        self.db.flush()
        self.db.refresh(initiative)
        return initiative
