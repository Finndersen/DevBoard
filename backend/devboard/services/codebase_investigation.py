"""Service for codebase investigation and architecture document generation."""

import logging
from dataclasses import dataclass
from pathlib import Path

import logfire

from devboard.agents.engines.gemini_cli import GeminiCliError, execute_gemini_prompt
from devboard.services.template_service import TemplateService, TemplateType
from devboard.utils.hash import compute_content_hash

logger = logging.getLogger(__name__)


@dataclass
class ArchitectureStatus:
    """Status of architecture document for a codebase."""

    exists: bool
    file_path: Path | None = None
    size_bytes: int | None = None


@dataclass
class ArchitectureGenerationResult:
    """Result of architecture document generation."""

    success: bool
    file_path: Path | None = None
    content: str | None = None
    error_message: str | None = None
    error_type: str | None = None


@dataclass
class ArchitectureDocument:
    """Complete architecture document information."""

    exists: bool
    content: str | None = None
    content_hash: str | None = None
    file_path: Path | None = None
    size_bytes: int | None = None


@dataclass
class ArchitectureUpdateResult:
    """Result of architecture document update."""

    success: bool
    content_hash: str | None = None
    message: str | None = None
    error_type: str | None = None
    current_hash: str | None = None


class CodebaseInvestigationService:
    """Service for investigating codebases and managing architecture documentation."""

    ARCHITECTURE_FILENAME = "ARCHITECTURE.md"

    def __init__(self, template_service: TemplateService):
        self.template_service = template_service

    def check_architecture_exists(self, codebase_path: str) -> ArchitectureStatus:
        """Check if architecture document exists for a codebase."""
        with logfire.span("codebase_investigation.check_architecture_exists", codebase_path=codebase_path):
            try:
                codebase_dir = Path(codebase_path).resolve()
                if not codebase_dir.exists() or not codebase_dir.is_dir():
                    logfire.warn("Codebase path does not exist or is not a directory", path=str(codebase_dir))
                    return ArchitectureStatus(exists=False)

                arch_file = codebase_dir / self.ARCHITECTURE_FILENAME
                if arch_file.exists() and arch_file.is_file():
                    size = arch_file.stat().st_size
                    logfire.info("Architecture document found", path=str(arch_file), size_bytes=size)
                    return ArchitectureStatus(exists=True, file_path=arch_file, size_bytes=size)
                else:
                    logfire.info("Architecture document not found", expected_path=str(arch_file))
                    return ArchitectureStatus(exists=False)

            except Exception as e:
                logger.error(f"Error checking architecture document for {codebase_path}: {e}")
                return ArchitectureStatus(exists=False)

    def read_architecture_content(self, codebase_path: str) -> str | None:
        """Read the content of the architecture document if it exists."""
        with logfire.span("codebase_investigation.read_architecture_content", codebase_path=codebase_path):
            try:
                status = self.check_architecture_exists(codebase_path)
                if not status.exists or not status.file_path:
                    return None

                content = status.file_path.read_text(encoding="utf-8")
                logfire.info("Architecture content read successfully", content_length=len(content))
                return content

            except Exception as e:
                logger.error(f"Error reading architecture document for {codebase_path}: {e}")
                return None

    def get_architecture_document(self, codebase_path: str) -> ArchitectureDocument:
        """Get complete architecture document information including content and hash."""
        with logfire.span("codebase_investigation.get_architecture_document", codebase_path=codebase_path):
            try:
                codebase_dir = Path(codebase_path).resolve()
                if not codebase_dir.exists() or not codebase_dir.is_dir():
                    logfire.warn("Codebase path does not exist or is not a directory", path=str(codebase_dir))
                    return ArchitectureDocument(exists=False)

                arch_file = codebase_dir / self.ARCHITECTURE_FILENAME
                if arch_file.exists() and arch_file.is_file():
                    content = arch_file.read_text(encoding="utf-8")
                    content_hash = compute_content_hash(content)
                    size = arch_file.stat().st_size

                    logfire.info(
                        "Architecture document found",
                        path=str(arch_file),
                        size_bytes=size,
                        content_hash=content_hash,
                    )

                    return ArchitectureDocument(
                        exists=True,
                        content=content,
                        content_hash=content_hash,
                        file_path=arch_file,
                        size_bytes=size,
                    )
                else:
                    logfire.info("Architecture document not found", expected_path=str(arch_file))
                    return ArchitectureDocument(exists=False)

            except Exception as e:
                logger.error(f"Error getting architecture document for {codebase_path}: {e}")
                return ArchitectureDocument(exists=False)

    def update_architecture_content(
        self, codebase_path: str, new_content: str, original_hash: str | None
    ) -> ArchitectureUpdateResult:
        """Update architecture document with conflict detection."""
        with logfire.span(
            "codebase_investigation.update_architecture_content",
            codebase_path=codebase_path,
            has_original_hash=original_hash is not None,
        ):
            try:
                codebase_dir = Path(codebase_path).resolve()
                if not codebase_dir.exists() or not codebase_dir.is_dir():
                    error_msg = f"Codebase path does not exist or is not a directory: {codebase_path}"
                    logfire.error("Invalid codebase path", error=error_msg)
                    return ArchitectureUpdateResult(success=False, message=error_msg, error_type="invalid_path")

                arch_file = codebase_dir / self.ARCHITECTURE_FILENAME

                # Check for conflicts if original_hash is provided
                if original_hash is not None:
                    if arch_file.exists():
                        current_content = arch_file.read_text(encoding="utf-8")
                        current_hash = compute_content_hash(current_content)

                        if current_hash != original_hash:
                            logfire.warn(
                                "Architecture document conflict detected",
                                original_hash=original_hash,
                                current_hash=current_hash,
                            )
                            return ArchitectureUpdateResult(
                                success=False,
                                message="The architecture document has been modified by another process. Please review the changes and try again.",
                                error_type="conflict",
                                current_hash=current_hash,
                            )
                    else:
                        # File was deleted after user started editing
                        return ArchitectureUpdateResult(
                            success=False,
                            message="The architecture document was deleted while you were editing.",
                            error_type="file_deleted",
                        )
                else:
                    # New document creation - check it doesn't already exist
                    if arch_file.exists():
                        current_content = arch_file.read_text(encoding="utf-8")
                        current_hash = compute_content_hash(current_content)
                        return ArchitectureUpdateResult(
                            success=False,
                            message="Architecture document already exists. Please refresh and edit the existing document.",
                            error_type="already_exists",
                            current_hash=current_hash,
                        )

                # Write the new content
                arch_file.write_text(new_content, encoding="utf-8")
                new_hash = compute_content_hash(new_content)

                logfire.info(
                    "Architecture document updated successfully",
                    file_path=str(arch_file),
                    content_length=len(new_content),
                    new_hash=new_hash,
                )

                return ArchitectureUpdateResult(
                    success=True,
                    content_hash=new_hash,
                    message="Architecture document updated successfully",
                )

            except Exception as e:
                error_msg = f"Error updating architecture document: {e}"
                logger.error(f"Error updating architecture document for {codebase_path}: {e}")
                return ArchitectureUpdateResult(success=False, message=error_msg, error_type="unexpected_error")

    async def generate_architecture_document(
        self,
        codebase_path: str,
        codebase_name: str,
    ) -> ArchitectureGenerationResult:
        """Generate or update architecture document for a codebase."""
        with logfire.span(
            "codebase_investigation.generate_architecture_document",
            codebase_path=codebase_path,
            codebase_name=codebase_name,
        ):
            try:
                codebase_dir = Path(codebase_path).resolve()
                if not codebase_dir.exists() or not codebase_dir.is_dir():
                    error_msg = f"Codebase path does not exist or is not a directory: {codebase_path}"
                    logfire.error("Invalid codebase path", error=error_msg)
                    return ArchitectureGenerationResult(
                        success=False, error_message=error_msg, error_type="invalid_path"
                    )

                arch_file = codebase_dir / self.ARCHITECTURE_FILENAME

                # Generate the architecture document using AI
                prompt = self._build_architecture_prompt(codebase_name)

                logfire.info(
                    "Starting architecture generation with AI",
                    codebase=codebase_name,
                    working_dir=str(codebase_dir),
                )

                ai_content = await execute_gemini_prompt(
                    prompt=prompt,
                    model="gemini-2.5-flash",
                    working_dir=str(codebase_dir),
                    timeout=120.0,  # Longer timeout for comprehensive analysis
                    operation_mode="read_only",
                )

                # Write the generated content to file
                arch_file.write_text(ai_content, encoding="utf-8")

                logfire.info(
                    "Architecture document generated successfully",
                    file_path=str(arch_file),
                    content_length=len(ai_content),
                )

                return ArchitectureGenerationResult(success=True, file_path=arch_file, content=ai_content)

            except GeminiCliError as e:
                error_msg = f"AI generation failed: {e}"
                logger.error(error_msg)
                logfire.error("Gemini CLI error during architecture generation", error=str(e))
                return ArchitectureGenerationResult(
                    success=False, error_message=error_msg, error_type="ai_generation_error"
                )
            except Exception as e:
                error_msg = f"Unexpected error generating architecture document: {e}"
                logger.error(error_msg)
                logfire.error("Unexpected error during architecture generation", error=str(e))
                return ArchitectureGenerationResult(
                    success=False, error_message=error_msg, error_type="unexpected_error"
                )

    def _build_architecture_prompt(self, codebase_name: str) -> str:
        """Build the prompt for architecture document generation."""
        template_content = self.template_service.get_template(TemplateType.ARCHITECTURE_DOCUMENT)

        prompt = f"""
You are analyzing the codebase '{codebase_name}' to generate comprehensive architecture documentation.

Please create a detailed ARCHITECTURE.md document with the following structure in Markdown format:

{template_content}

Focus on providing specific, actionable information about the codebase structure and implementation details.
Analyze the actual code files to provide accurate information about the current implementation.
If this is a web application or API service, pay special attention to the API endpoints and document them thoroughly.

Replace [CODEBASE NAME] with the actual codebase name: {codebase_name}.

You are not allowed to edit files directly, instead provide the full content of the ARCHITECTURE.md file as your response.
"""

        return prompt
