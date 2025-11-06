"""Repository for conversation evaluation data access operations."""

from datetime import datetime

from sqlalchemy import select

from devboard.db.models.conversation_evaluation import ConversationEvaluation
from devboard.db.repositories.base import BaseRepository


class ConversationEvaluationRepository(BaseRepository[ConversationEvaluation]):
    """Repository for conversation evaluation data access operations."""

    def get_by_id(self, evaluation_id: int) -> ConversationEvaluation | None:
        """Get an evaluation by its ID.

        Args:
            evaluation_id: The evaluation ID to search for

        Returns:
            ConversationEvaluation instance if found, None otherwise
        """
        stmt = select(ConversationEvaluation).where(ConversationEvaluation.id == evaluation_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_conversation_id(
        self, conversation_id: int, limit: int | None = None
    ) -> list[ConversationEvaluation]:
        """Get all evaluations for a conversation.

        Args:
            conversation_id: The conversation ID to search for
            limit: Optional limit on number of results (most recent first)

        Returns:
            List of ConversationEvaluation instances ordered by evaluated_at descending
        """
        stmt = (
            select(ConversationEvaluation)
            .where(ConversationEvaluation.conversation_id == conversation_id)
            .order_by(ConversationEvaluation.evaluated_at.desc())
        )

        if limit:
            stmt = stmt.limit(limit)

        return list(self.db.execute(stmt).scalars().all())

    def get_latest_by_conversation_id(self, conversation_id: int) -> ConversationEvaluation | None:
        """Get the most recent evaluation for a conversation.

        Args:
            conversation_id: The conversation ID to search for

        Returns:
            Latest ConversationEvaluation instance if found, None otherwise
        """
        stmt = (
            select(ConversationEvaluation)
            .where(ConversationEvaluation.conversation_id == conversation_id)
            .order_by(ConversationEvaluation.evaluated_at.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_rating_range(
        self, min_rating: float, max_rating: float, limit: int | None = None
    ) -> list[ConversationEvaluation]:
        """Get evaluations within a rating range.

        Args:
            min_rating: Minimum overall rating (inclusive)
            max_rating: Maximum overall rating (inclusive)
            limit: Optional limit on number of results

        Returns:
            List of ConversationEvaluation instances ordered by rating descending
        """
        stmt = (
            select(ConversationEvaluation)
            .where(
                ConversationEvaluation.overall_rating >= min_rating,
                ConversationEvaluation.overall_rating <= max_rating,
            )
            .order_by(ConversationEvaluation.overall_rating.desc())
        )

        if limit:
            stmt = stmt.limit(limit)

        return list(self.db.execute(stmt).scalars().all())

    def get_by_date_range(
        self, start_date: datetime, end_date: datetime, limit: int | None = None
    ) -> list[ConversationEvaluation]:
        """Get evaluations within a date range.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            limit: Optional limit on number of results

        Returns:
            List of ConversationEvaluation instances ordered by evaluated_at descending
        """
        stmt = (
            select(ConversationEvaluation)
            .where(
                ConversationEvaluation.evaluated_at >= start_date,
                ConversationEvaluation.evaluated_at <= end_date,
            )
            .order_by(ConversationEvaluation.evaluated_at.desc())
        )

        if limit:
            stmt = stmt.limit(limit)

        return list(self.db.execute(stmt).scalars().all())

    def create(
        self,
        conversation_id: int,
        evaluator_model_id: str,
        overall_rating: float,
        evaluations_json: dict,
        summary: str,
    ) -> ConversationEvaluation:
        """Create a new evaluation record.

        Args:
            conversation_id: ID of the conversation being evaluated
            evaluator_model_id: Model used for evaluation
            overall_rating: Overall performance rating (0-10)
            evaluations_json: Complete PerformanceEvaluations as JSON dict
            summary: Executive summary text

        Returns:
            Created ConversationEvaluation instance with assigned ID
        """
        evaluation = ConversationEvaluation(
            conversation_id=conversation_id,
            evaluator_model_id=evaluator_model_id,
            overall_rating=overall_rating,
            evaluations_json=evaluations_json,
            summary=summary,
        )
        self.db.add(evaluation)
        self.db.flush()
        return evaluation

    def delete(self, evaluation_id: int) -> bool:
        """Delete an evaluation by ID.

        Args:
            evaluation_id: ID of evaluation to delete

        Returns:
            True if evaluation was deleted, False if not found
        """
        evaluation = self.get_by_id(evaluation_id)
        if evaluation:
            self.db.delete(evaluation)
            self.db.flush()
            return True
        return False

    def count_by_conversation_id(self, conversation_id: int) -> int:
        """Count number of evaluations for a conversation.

        Args:
            conversation_id: The conversation ID to count for

        Returns:
            Number of evaluations
        """
        from sqlalchemy import func

        stmt = select(func.count()).select_from(ConversationEvaluation).where(
            ConversationEvaluation.conversation_id == conversation_id
        )
        return self.db.execute(stmt).scalar_one()
