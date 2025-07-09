"""Utilities for Firecrawl skill content indexing and querying."""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from intentkit.abstracts.skill import SkillStoreABC

logger = logging.getLogger(__name__)


class FirecrawlDocumentProcessor:
    """Handles document processing and sanitization for Firecrawl content."""

    @staticmethod
    def sanitize_for_database(text: str) -> str:
        """Sanitize text content to prevent database storage errors."""
        if not text:
            return ""

        # Remove null bytes and other problematic characters
        text = text.replace("\x00", "")
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)
        text = text.strip()

        return text

    @staticmethod
    def split_documents(
        documents: List[Document], chunk_size: int = 1000, chunk_overlap: int = 200
    ) -> List[Document]:
        """Split documents into smaller chunks for better indexing."""
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
        )

        split_docs = []
        for doc in documents:
            # Sanitize content before splitting
            sanitized_content = FirecrawlDocumentProcessor.sanitize_for_database(
                doc.page_content
            )
            doc.page_content = sanitized_content

            # Split the document
            chunks = text_splitter.split_documents([doc])
            split_docs.extend(chunks)

        return split_docs


class FirecrawlVectorStoreManager:
    """Manages vector store operations for Firecrawl content."""

    def __init__(self, skill_store: SkillStoreABC):
        self.skill_store = skill_store

    def create_embeddings(self) -> OpenAIEmbeddings:
        """Create OpenAI embeddings instance."""
        openai_api_key = self.skill_store.get_system_config("openai_api_key")
        if not openai_api_key:
            raise ValueError("OpenAI API key not found in system configuration")

        return OpenAIEmbeddings(
            openai_api_key=openai_api_key, model="text-embedding-3-small"
        )

    def encode_vector_store(self, vector_store: FAISS) -> Dict[str, str]:
        """Encode FAISS vector store to base64 for storage (compatible with web_scraper)."""
        import base64
        import os
        import tempfile

        try:
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
        except Exception as e:
            logger.error(f"Error encoding vector store: {e}")
            raise

    def decode_vector_store(
        self, encoded_files: Dict[str, str], embeddings: OpenAIEmbeddings
    ) -> FAISS:
        """Decode base64 files back to FAISS vector store (compatible with web_scraper)."""
        import base64
        import os
        import tempfile

        try:
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
        except Exception as e:
            logger.error(f"Error decoding vector store: {e}")
            raise

    async def load_vector_store(self, agent_id: str) -> Optional[FAISS]:
        """Load existing vector store for an agent."""
        try:
            vector_store_key = f"vector_store_{agent_id}"
            stored_data = await self.skill_store.get_agent_skill_data(
                agent_id, "web_scraper", vector_store_key
            )

            if not stored_data or "faiss_files" not in stored_data:
                return None

            embeddings = self.create_embeddings()
            return self.decode_vector_store(stored_data["faiss_files"], embeddings)

        except Exception as e:
            logger.error(f"Error loading vector store for agent {agent_id}: {e}")
            return None

    async def save_vector_store(
        self,
        agent_id: str,
        vector_store: FAISS,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> None:
        """Save vector store for an agent (compatible with web_scraper format)."""
        try:
            vector_store_key = f"vector_store_{agent_id}"
            encoded_files = self.encode_vector_store(vector_store)

            # Use the same data structure as web_scraper
            storage_data = {
                "faiss_files": encoded_files,
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
            }

            await self.skill_store.save_agent_skill_data(
                agent_id, "web_scraper", vector_store_key, storage_data
            )

        except Exception as e:
            logger.error(f"Error saving vector store for agent {agent_id}: {e}")
            raise


class FirecrawlMetadataManager:
    """Manages metadata for Firecrawl indexed content."""

    def __init__(self, skill_store: SkillStoreABC):
        self.skill_store = skill_store

    def create_url_metadata(
        self, urls: List[str], documents: List[Document], source_type: str
    ) -> Dict[str, Any]:
        """Create metadata for indexed URLs."""
        return {
            "urls": urls,
            "document_count": len(documents),
            "source_type": source_type,
            "indexed_at": str(len(urls)),  # Simple counter
        }

    async def update_metadata(
        self, agent_id: str, new_metadata: Dict[str, Any]
    ) -> None:
        """Update metadata for an agent."""
        try:
            metadata_key = f"indexed_urls_{agent_id}"
            await self.skill_store.save_agent_skill_data(
                agent_id, "web_scraper", metadata_key, new_metadata
            )
        except Exception as e:
            logger.error(f"Error updating metadata for agent {agent_id}: {e}")
            raise


async def index_documents(
    documents: List[Document],
    agent_id: str,
    skill_store: SkillStoreABC,
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
) -> Tuple[int, bool]:
    """
    Index documents into the Firecrawl vector store.

    Args:
        documents: List of documents to index
        agent_id: Agent ID for storage
        skill_store: Skill store for persistence
        chunk_size: Size of text chunks
        chunk_overlap: Overlap between chunks

    Returns:
        Tuple of (total_chunks, was_merged_with_existing)
    """
    try:
        # Initialize managers
        vs_manager = FirecrawlVectorStoreManager(skill_store)

        # Split documents into chunks
        split_docs = FirecrawlDocumentProcessor.split_documents(
            documents, chunk_size, chunk_overlap
        )

        if not split_docs:
            logger.warning("No documents to index after splitting")
            return 0, False

        # Create embeddings
        embeddings = vs_manager.create_embeddings()

        # Try to load existing vector store
        existing_vector_store = await vs_manager.load_vector_store(agent_id)

        if existing_vector_store:
            # Add to existing vector store
            existing_vector_store.add_documents(split_docs)
            vector_store = existing_vector_store
            was_merged = True
        else:
            # Create new vector store
            vector_store = FAISS.from_documents(split_docs, embeddings)
            was_merged = False

        # Save the vector store
        await vs_manager.save_vector_store(
            agent_id, vector_store, chunk_size, chunk_overlap
        )

        logger.info(
            f"Successfully indexed {len(split_docs)} chunks for agent {agent_id}"
        )
        return len(split_docs), was_merged

    except Exception as e:
        logger.error(f"Error indexing documents for agent {agent_id}: {e}")
        raise


async def query_indexed_content(
    query: str,
    agent_id: str,
    skill_store: SkillStoreABC,
    max_results: int = 4,
) -> List[Document]:
    """
    Query the Firecrawl indexed content.

    Args:
        query: Search query
        agent_id: Agent ID
        skill_store: Skill store for persistence
        max_results: Maximum number of results to return

    Returns:
        List of relevant documents
    """
    try:
        # Initialize vector store manager
        vs_manager = FirecrawlVectorStoreManager(skill_store)

        # Load vector store
        vector_store = await vs_manager.load_vector_store(agent_id)

        if not vector_store:
            logger.warning(f"No vector store found for agent {agent_id}")
            return []

        # Perform similarity search
        docs = vector_store.similarity_search(query, k=max_results)

        logger.info(f"Found {len(docs)} documents for query: {query}")
        return docs

    except Exception as e:
        logger.error(f"Error querying indexed content for agent {agent_id}: {e}")
        raise
