"""
Utility functions for web scraper skills.

This module contains common functionality used across all web scraper skills
to reduce code duplication and improve maintainability.
"""

import asyncio
import base64
import logging
import os
import tempfile
from typing import Dict, List, Optional, Tuple

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from intentkit.abstracts.skill import SkillStoreABC

logger = logging.getLogger(__name__)

# Constants
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200
DEFAULT_REQUEST_TIMEOUT = 30
DEFAULT_REQUESTS_PER_SECOND = 2
MAX_CONTENT_SIZE_MB = 10  # 10 MB limit
MAX_CONTENT_SIZE_BYTES = MAX_CONTENT_SIZE_MB * 1024 * 1024

# HTTP Headers to bypass Cloudflare and other bot protection
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

# Alternative headers for fallback when primary headers fail
FALLBACK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

# Storage keys
VECTOR_STORE_KEY_PREFIX = "vector_store"
METADATA_KEY_PREFIX = "indexed_urls"


class VectorStoreManager:
    """Manages vector store operations including creation, saving, loading, and merging."""

    def __init__(self, skill_store: SkillStoreABC):
        self.skill_store = skill_store

    def create_embeddings(self) -> OpenAIEmbeddings:
        """Create OpenAI embeddings using system API key."""
        api_key = self.skill_store.get_system_config("openai_api_key")
        return OpenAIEmbeddings(api_key=api_key)

    def get_storage_keys(self, agent_id: str) -> Tuple[str, str]:
        """Get storage keys for vector store and metadata."""
        vector_store_key = f"{VECTOR_STORE_KEY_PREFIX}_{agent_id}"
        metadata_key = f"{METADATA_KEY_PREFIX}_{agent_id}"
        return vector_store_key, metadata_key

    def encode_vector_store(self, vector_store: FAISS) -> Dict[str, str]:
        """Encode FAISS vector store to base64 for storage."""
        with tempfile.TemporaryDirectory() as temp_dir:
            vector_store.save_local(temp_dir)

            encoded_files = {}
            for filename in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, filename)
                if os.path.isfile(file_path):
                    with open(file_path, "rb") as f:
                        encoded_files[filename] = base64.b64encode(f.read()).decode(
                            "utf-8"
                        )

            return encoded_files

    def decode_vector_store(
        self, encoded_files: Dict[str, str], embeddings: OpenAIEmbeddings
    ) -> FAISS:
        """Decode base64 files back to FAISS vector store."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Decode and write files
            for filename, encoded_content in encoded_files.items():
                file_path = os.path.join(temp_dir, filename)
                with open(file_path, "wb") as f:
                    f.write(base64.b64decode(encoded_content))

            # Load vector store
            return FAISS.load_local(
                temp_dir,
                embeddings,
                allow_dangerous_deserialization=True,
            )

    async def get_existing_vector_store(self, agent_id: str) -> Optional[Dict]:
        """Get existing vector store data if it exists."""
        vector_store_key, _ = self.get_storage_keys(agent_id)
        return await self.skill_store.get_agent_skill_data(
            agent_id, "web_scraper", vector_store_key
        )

    async def merge_with_existing(
        self,
        new_documents: List[Document],
        agent_id: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> Tuple[FAISS, bool]:
        """
        Merge new documents with existing vector store or create new one.

        Returns:
            Tuple of (vector_store, was_merged)
        """
        embeddings = self.create_embeddings()
        existing_data = await self.get_existing_vector_store(agent_id)

        if existing_data and "faiss_files" in existing_data:
            try:
                logger.info(f"[{agent_id}] Merging content with existing vector store")

                # Create new vector store from new documents
                new_vector_store = FAISS.from_documents(new_documents, embeddings)

                # Load existing vector store
                existing_vector_store = self.decode_vector_store(
                    existing_data["faiss_files"], embeddings
                )

                # Merge stores
                existing_vector_store.merge_from(new_vector_store)
                return existing_vector_store, True

            except Exception as e:
                logger.warning(
                    f"[{agent_id}] Merge failed, creating new vector store: {e}"
                )
            logger.info(f"[{agent_id}] Creating new vector store")

        # Create new vector store
        logger.info(f"[{agent_id}] Creating new vector store")
        vector_store = FAISS.from_documents(new_documents, embeddings)
        return vector_store, False

    async def save_vector_store(
        self,
        vector_store: FAISS,
        agent_id: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> None:
        """Save vector store to agent skill data."""
        vector_store_key, _ = self.get_storage_keys(agent_id)

        logger.info(f"[{agent_id}] Saving vector store")

        # Encode vector store
        encoded_files = self.encode_vector_store(vector_store)

        # Prepare data for storage
        storage_data = {
            "faiss_files": encoded_files,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
        }

        try:
            # Save to storage
            await self.skill_store.save_agent_skill_data(
                agent_id=agent_id,
                skill="web_scraper",
                key=vector_store_key,
                data=storage_data,
            )

            logger.info(f"[{agent_id}] Successfully saved vector store")

        except Exception as e:
            logger.error(f"[{agent_id}] Failed to save vector store: {e}")
            raise

    async def load_vector_store(self, agent_id: str) -> Optional[FAISS]:
        """Load vector store for an agent."""
        stored_data = await self.get_existing_vector_store(agent_id)

        if not stored_data or "faiss_files" not in stored_data:
            return None

        try:
            embeddings = self.create_embeddings()
            return self.decode_vector_store(stored_data["faiss_files"], embeddings)
        except Exception as e:
            logger.error(f"Error loading vector store for agent {agent_id}: {e}")
            return None

    async def get_content_size(self, agent_id: str) -> int:
        """Get the current content size in bytes for an agent."""
        stored_data = await self.get_existing_vector_store(agent_id)
        if not stored_data:
            return 0

        # Calculate size from stored FAISS files
        total_size = 0
        if "faiss_files" in stored_data:
            for encoded_content in stored_data["faiss_files"].values():
                # Base64 encoded content size (approximate original size)
                total_size += len(base64.b64decode(encoded_content))

        return total_size

    def format_size(self, size_bytes: int) -> str:
        """Format size in bytes to human readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"


class DocumentProcessor:
    """Handles document processing operations."""

    @staticmethod
    def create_chunks(
        documents: List[Document],
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> List[Document]:
        """Split documents into chunks."""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )
        return text_splitter.split_documents(documents)

    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text content."""
        lines = text.split("\n")
        cleaned_lines = []

        for line in lines:
            cleaned_line = line.strip()
            if cleaned_line:
                cleaned_lines.append(cleaned_line)

        cleaned_text = "\n".join(cleaned_lines)

        # Remove excessive consecutive newlines
        while "\n\n\n" in cleaned_text:
            cleaned_text = cleaned_text.replace("\n\n\n", "\n\n")

        return cleaned_text.strip()

    @staticmethod
    def validate_content(content: str, min_length: int = 10) -> bool:
        """Validate content meets minimum requirements."""
        return len(content.strip()) >= min_length

    @staticmethod
    def create_document(
        content: str,
        title: str,
        source: str,
        tags: str = "",
        extra_metadata: Optional[Dict] = None,
    ) -> Document:
        """Create a Document with standardized metadata."""
        cleaned_content = DocumentProcessor.clean_text(content)

        # Parse tags
        tag_list = (
            [tag.strip() for tag in tags.split(",") if tag.strip()] if tags else []
        )

        metadata = {
            "title": title,
            "source": source,
            "source_type": "manual",
            "tags": tag_list,
            "length": len(cleaned_content),
            "indexed_at": str(asyncio.get_event_loop().time()),
        }

        # Add extra metadata if provided
        if extra_metadata:
            metadata.update(extra_metadata)

        return Document(page_content=cleaned_content, metadata=metadata)


class MetadataManager:
    """Manages metadata for indexed content."""

    def __init__(self, skill_store: SkillStoreABC):
        self.skill_store = skill_store

    async def get_existing_metadata(self, agent_id: str) -> Dict:
        """Get existing metadata for an agent."""
        vs_manager = VectorStoreManager(self.skill_store)
        _, metadata_key = vs_manager.get_storage_keys(agent_id)
        return (
            await self.skill_store.get_agent_skill_data(
                agent_id, "web_scraper", metadata_key
            )
            or {}
        )

    def create_url_metadata(
        self,
        urls: List[str],
        split_docs: List[Document],
        source_type: str = "web_scraper",
        extra_fields: Optional[Dict] = None,
    ) -> Dict:
        """Create metadata for a list of URLs."""
        metadata = {}
        current_time = str(asyncio.get_event_loop().time())

        for url in urls:
            url_metadata = {
                "indexed_at": current_time,
                "chunks": len(
                    [doc for doc in split_docs if doc.metadata.get("source") == url]
                ),
                "source_type": source_type,
            }

            if extra_fields:
                url_metadata.update(extra_fields)

            metadata[url] = url_metadata

        return metadata

    def create_document_metadata(
        self,
        title: str,
        source: str,
        tags: str,
        split_docs: List[Document],
        document_length: int,
    ) -> Dict:
        """Create metadata for a document."""
        # Generate unique key
        key = f"document_{title.lower().replace(' ', '_')}"

        return {
            key: {
                "title": title,
                "source": source,
                "source_type": "document_indexer",
                "tags": [tag.strip() for tag in tags.split(",") if tag.strip()]
                if tags
                else [],
                "indexed_at": str(asyncio.get_event_loop().time()),
                "chunks": len(split_docs),
                "length": document_length,
            }
        }

    async def update_metadata(self, agent_id: str, new_metadata: Dict) -> None:
        """Update metadata for an agent."""
        vs_manager = VectorStoreManager(self.skill_store)
        _, metadata_key = vs_manager.get_storage_keys(agent_id)

        # Get existing metadata
        existing_metadata = await self.get_existing_metadata(agent_id)

        # Update with new metadata
        existing_metadata.update(new_metadata)

        # Save updated metadata
        await self.skill_store.save_agent_skill_data(
            agent_id=agent_id,
            skill="web_scraper",
            key=metadata_key,
            data=existing_metadata,
        )


class ResponseFormatter:
    """Formats consistent responses for web scraper skills."""

    @staticmethod
    def format_indexing_response(
        operation_type: str,
        urls_or_content: List[str] | str,
        total_chunks: int,
        chunk_size: int,
        chunk_overlap: int,
        was_merged: bool,
        extra_info: Optional[Dict] = None,
        current_size_bytes: int = 0,
        size_limit_reached: bool = False,
        total_requested_urls: int = 0,
    ) -> str:
        """Format a consistent response for indexing operations."""

        # Handle both URL lists and single content
        if isinstance(urls_or_content, list):
            urls = urls_or_content
            processed_count = len(urls)

            if size_limit_reached and total_requested_urls > 0:
                content_summary = f"Processed {processed_count} of {total_requested_urls} URLs (size limit reached)"
            else:
                content_summary = (
                    f"Successfully {operation_type} {processed_count} URLs"
                )

            if len(urls) <= 5:
                url_list = "\n".join([f"- {url}" for url in urls])
            else:
                displayed_urls = urls[:5]
                remaining_count = len(urls) - 5
                url_list = "\n".join([f"- {url}" for url in displayed_urls])
                url_list += f"\n... and {remaining_count} more"
        else:
            content_summary = f"Successfully {operation_type} content"
            url_list = ""

        # Build response
        response_parts = [content_summary]

        if url_list:
            response_parts.append(url_list)

        response_parts.extend(
            [
                f"Total chunks created: {total_chunks}",
                f"Chunk size: {chunk_size} characters",
                f"Chunk overlap: {chunk_overlap} characters",
                f"Vector store: {'merged with existing content' if was_merged else 'created new index'}",
            ]
        )

        # Add size information
        if current_size_bytes > 0:
            vs_manager = VectorStoreManager(None)  # Just for formatting
            formatted_size = vs_manager.format_size(current_size_bytes)
            max_size = vs_manager.format_size(MAX_CONTENT_SIZE_BYTES)
            response_parts.append(
                f"Current storage size: {formatted_size} / {max_size}"
            )

        if size_limit_reached:
            response_parts.append("Size limit reached - some URLs were not processed")

        if extra_info:
            for key, value in extra_info.items():
                response_parts.append(f"{key}: {value}")

        response_parts.append(
            "All content has been indexed and can be queried using the query_indexed_content tool."
        )

        return "\n".join(response_parts)


async def scrape_and_index_urls(
    urls: List[str],
    agent_id: str,
    skill_store: SkillStoreABC,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    requests_per_second: int = DEFAULT_REQUESTS_PER_SECOND,
) -> Tuple[int, bool, List[str]]:
    """
    Scrape URLs and index their content into vector store with size limits.

    Args:
        urls: List of URLs to scrape
        agent_id: Agent identifier for storage
        skill_store: Skill store instance
        chunk_size: Size of text chunks
        chunk_overlap: Overlap between chunks
        requests_per_second: Rate limiting for requests

    Returns:
        Tuple of (total_chunks, was_merged, valid_urls)
    """
    from urllib.parse import urlparse

    from langchain_community.document_loaders import WebBaseLoader

    # Validate URLs
    valid_urls = []
    for url in urls:
        try:
            parsed = urlparse(url)
            if parsed.scheme in ["http", "https"] and parsed.netloc:
                valid_urls.append(url)
            else:
                logger.warning(f"Invalid URL format: {url}")
        except Exception as e:
            logger.warning(f"Error parsing URL {url}: {e}")

    if not valid_urls:
        return 0, False, []

    # Check existing content size
    vs_manager = VectorStoreManager(skill_store)
    current_size = await vs_manager.get_content_size(agent_id)

    logger.info(
        f"[{agent_id}] Current storage size: {vs_manager.format_size(current_size)}"
    )

    if current_size >= MAX_CONTENT_SIZE_BYTES:
        logger.warning(
            f"[{agent_id}] Storage limit already reached: {vs_manager.format_size(current_size)}"
        )
        return 0, False, []

    # Process URLs one by one with size checking
    processed_urls = []
    total_chunks = 0
    was_merged = False
    size_limit_reached = False

    for i, url in enumerate(valid_urls):
        if current_size >= MAX_CONTENT_SIZE_BYTES:
            size_limit_reached = True
            logger.warning(f"[{agent_id}] Size limit reached after processing {i} URLs")
            break

        try:
            logger.info(f"[{agent_id}] Processing URL {i + 1}/{len(valid_urls)}: {url}")

            # Load single URL with enhanced headers
            loader = WebBaseLoader(
                web_paths=[url],
                requests_per_second=requests_per_second,
            )

            # Configure loader with enhanced headers to bypass bot protection
            loader.requests_kwargs = {
                "verify": True,
                "timeout": DEFAULT_REQUEST_TIMEOUT,
                "headers": DEFAULT_HEADERS,
            }

            # Scrape the URL with retry logic
            documents = None
            try:
                documents = await asyncio.to_thread(loader.load)
            except Exception as primary_error:
                # If primary headers fail, try fallback headers
                logger.warning(
                    f"[{agent_id}] Primary headers failed for {url}, trying fallback: {primary_error}"
                )

                loader.requests_kwargs["headers"] = FALLBACK_HEADERS
                try:
                    documents = await asyncio.to_thread(loader.load)
                    logger.info(f"[{agent_id}] Fallback headers succeeded for {url}")
                except Exception as fallback_error:
                    logger.error(
                        f"[{agent_id}] Both header sets failed for {url}: {fallback_error}"
                    )
                    raise fallback_error

            if not documents:
                logger.warning(f"[{agent_id}] No content extracted from {url}")
                continue

            # Check content size before processing
            content_size = sum(
                len(doc.page_content.encode("utf-8")) for doc in documents
            )

            if current_size + content_size > MAX_CONTENT_SIZE_BYTES:
                logger.warning(
                    f"[{agent_id}] Adding {url} would exceed size limit. Skipping."
                )
                size_limit_reached = True
                break

            # Process and index this URL's content
            chunks, merged = await index_documents(
                documents, agent_id, skill_store, chunk_size, chunk_overlap
            )

            if chunks > 0:
                processed_urls.append(url)
                total_chunks += chunks
                was_merged = merged or was_merged
                current_size += content_size

                logger.info(
                    f"[{agent_id}] Processed {url}: {chunks} chunks, current size: {vs_manager.format_size(current_size)}"
                )

            # Add delay for rate limiting
            if i < len(valid_urls) - 1:  # Don't delay after the last URL
                await asyncio.sleep(1.0 / requests_per_second)

        except Exception as e:
            logger.error(f"[{agent_id}] Error processing {url}: {e}")
            continue

    # Log final results
    if size_limit_reached:
        logger.warning(
            f"[{agent_id}] Size limit reached. Processed {len(processed_urls)}/{len(valid_urls)} URLs"
        )
    else:
        logger.info(
            f"[{agent_id}] Successfully processed all {len(processed_urls)} URLs"
        )

    return total_chunks, was_merged, processed_urls


# Convenience function that combines all operations
async def index_documents(
    documents: List[Document],
    agent_id: str,
    skill_store: SkillStoreABC,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> Tuple[int, bool]:
    """
    Complete document indexing workflow.

    Returns:
        Tuple of (total_chunks, was_merged)
    """
    # Process documents
    split_docs = DocumentProcessor.create_chunks(documents, chunk_size, chunk_overlap)

    if not split_docs:
        raise ValueError("No content could be processed into chunks")

    # Handle vector store
    vs_manager = VectorStoreManager(skill_store)
    vector_store, was_merged = await vs_manager.merge_with_existing(
        split_docs, agent_id, chunk_size, chunk_overlap
    )

    # Save vector store
    await vs_manager.save_vector_store(
        vector_store, agent_id, chunk_size, chunk_overlap
    )

    return len(split_docs), was_merged


# Error handling decorator
def handle_skill_errors(operation_name: str):
    """Decorator for consistent error handling in skills."""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {operation_name}: {e}")
                return f"Error {operation_name}: {str(e)}"

        return wrapper

    return decorator
