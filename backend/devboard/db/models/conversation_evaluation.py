"""Conversation evaluation model for storing evaluation results."""

import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Float, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .conversation import Conversation


class ConversationEvaluation(Base):
    """Model for storing conversation evaluation results.

    Stores the complete evaluation output including scores, explanations,
    evidence, and improvement suggestions for tracking and analysis over time.

    Attributes:
        id: Primary key
        conversation_id: Foreign key to conversation being evaluated
        evaluator_model_id: Model used for evaluation (e.g., "anthropic:claude-sonnet-4")
        overall_rating: Overall performance rating (0-10)
        evaluations_json: Complete PerformanceEvaluations as JSON
        summary: Executive summary text
        evaluated_at: When the evaluation was performed
    """

    __tablename__ = "conversation_evaluations"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"), nullable=False)

    # Evaluator configuration
    evaluator_model_id: Mapped[str] = mapped_column(nullable=False)

    # Evaluation results
    overall_rating: Mapped[float] = mapped_column(Float, nullable=False)
    evaluations_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)  # PerformanceEvaluations
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    evaluated_at: Mapped[datetime.datetime] = mapped_column(default=lambda: datetime.datetime.now(datetime.UTC))

    # Relationships
    conversation: Mapped["Conversation"] = relationship(back_populates="evaluations")

    # Indexes for common queries
    __table_args__ = (
        Index("idx_evaluations_by_conversation", "conversation_id", "evaluated_at"),
        Index("idx_evaluations_by_rating", "overall_rating"),
        Index("idx_evaluations_by_date", "evaluated_at"),
    )

    @classmethod
    def from_evaluation_result(
        cls,
        conversation_id: int,
        evaluator_model_id: str,
        evaluation: "devboard.agents.evaluation_models.ConversationEvaluation",  # type: ignore
    ) -> "ConversationEvaluation":
        """Create a database model from an evaluation result.

        Args:
            conversation_id: ID of the evaluated conversation
            evaluator_model_id: Model ID used for evaluation
            evaluation: ConversationEvaluation result from service

        Returns:
            ConversationEvaluation database model instance
        """
        return cls(
            conversation_id=conversation_id,
            evaluator_model_id=evaluator_model_id,
            overall_rating=evaluation.overall_rating,
            evaluations_json=evaluation.evaluations.model_dump(mode="json"),
            summary=evaluation.summary,
        )

    def to_evaluation_result(self) -> "devboard.agents.evaluation_models.ConversationEvaluation":  # type: ignore
        """Convert database model to evaluation result.

        Returns:
            ConversationEvaluation Pydantic model
        """
        from devboard.agents.evaluation_models import ConversationEvaluation as EvalResult
        from devboard.agents.evaluation_models import PerformanceEvaluations

        return EvalResult(
            overall_rating=self.overall_rating,
            evaluations=PerformanceEvaluations.model_validate(self.evaluations_json),
            summary=self.summary,
        )
