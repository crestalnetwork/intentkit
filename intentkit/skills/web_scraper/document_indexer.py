import logging
from typing import Type

from pydantic import BaseModel, Field

from intentkit.skills.web_scraper.base import WebScraperBaseTool
from intentkit.skills.web_scraper.utils import (
    DocumentProcessor,
    MetadataManager,
    ResponseFormatter,
    VectorStoreManager,
    index_documents,
)

logger = logging.getLogger(__name__)


class DocumentIndexerInput(BaseModel):
    """Input for DocumentIndexer tool."""

    text_content: str = Field(
        description="The text content to add to the vector database. Can be content from Google Docs, Notion, or any other text source",
        min_length=10,
        max_length=100000,
    )
    title: str = Field(
        description="Title or name for this text content (will be used as metadata)",
        max_length=200,
    )
    source: str = Field(
        description="Source of the text content (e.g., 'Google Doc', 'Notion Page', 'Manual Entry')",
        default="Manual Entry",
        max_length=100,
    )
    chunk_size: int = Field(
        description="Size of text chunks for indexing (default: 1000)",
        default=1000,
        ge=100,
        le=4000,
    )
    chunk_overlap: int = Field(
        description="Overlap between chunks (default: 200)",
        default=200,
        ge=0,
        le=1000,
    )
    tags: str = Field(
        description="Optional tags for categorizing the content (comma-separated)",
        default="",
        max_length=500,
    )


class DocumentIndexer(WebScraperBaseTool):
    """Tool for importing and indexing document content to the vector database.

    This tool allows users to copy and paste document content from various sources
    (like Google Docs, Notion, PDFs, etc.) and index it directly into the vector store
    for later querying and retrieval.
    """

    name: str = "web_scraper_document_indexer"
    description: str = (
        "Import and index document content directly to the vector database. "
        "Perfect for adding content from Google Docs, Notion pages, PDFs, or any other document sources. "
        "The indexed content can then be queried using the query_indexed_content tool."
    )
    args_schema: Type[BaseModel] = DocumentIndexerInput

    async def _arun(
        self,
        text_content: str,
        title: str,
        source: str = "Manual Entry",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        tags: str = "",
        **kwargs,
    ) -> str:
        """Add text content to the vector database."""
        # Get agent context - throw error if not available
        # Configuration is always available in new runtime
        pass

        context = self.get_context()
        if not context or not context.agent_id:
            raise ValueError("Agent ID is required but not found in configuration")

        agent_id = context.agent_id

        logger.info(f"[{agent_id}] Starting document indexing for title: '{title}'")

        # Validate content
        if not DocumentProcessor.validate_content(text_content):
            logger.error(f"[{agent_id}] Content validation failed - too short")
            return "Error: Text content is too short. Please provide at least 10 characters of content."

        # Create document with metadata
        document = DocumentProcessor.create_document(
            text_content,
            title,
            source,
            tags,
            extra_metadata={"source_type": "document_indexer"},
        )

        logger.info(
            f"[{agent_id}] Document created, length: {len(document.page_content)} chars"
        )

        # Index the document
        total_chunks, was_merged = await index_documents(
            [document], agent_id, self.skill_store, chunk_size, chunk_overlap
        )

        # Get current storage size for response
        vs_manager = VectorStoreManager(self.skill_store)
        current_size = await vs_manager.get_content_size(agent_id)

        # Update metadata
        metadata_manager = MetadataManager(self.skill_store)
        new_metadata = metadata_manager.create_document_metadata(
            title, source, tags, [document], len(text_content)
        )
        await metadata_manager.update_metadata(agent_id, new_metadata)

        logger.info(f"[{agent_id}] Document indexing completed successfully")

        # Format response
        response = ResponseFormatter.format_indexing_response(
            "indexed",
            f"Document: {title}",
            total_chunks,
            chunk_size,
            chunk_overlap,
            was_merged,
            current_size_bytes=current_size,
        )

        logger.info(f"[{agent_id}] Document indexing completed successfully")
        return response
