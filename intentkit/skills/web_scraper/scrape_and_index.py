import asyncio
import base64
import logging
import os
import tempfile
from typing import List, Type
from urllib.parse import urlparse

from langchain_community.document_loaders import WebBaseLoader
from langchain_community.vectorstores import FAISS
from langchain_core.runnables import RunnableConfig
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field

from intentkit.skills.web_scraper.base import WebScraperBaseTool

logger = logging.getLogger(__name__)


class ScrapeAndIndexInput(BaseModel):
    """Input for ScrapeAndIndex tool."""

    urls: List[str] = Field(
        description="List of URLs to scrape and index. Each URL should be a valid web address starting with http:// or https://",
        min_items=1,
        max_items=10,
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


class QueryIndexInput(BaseModel):
    """Input for QueryIndex tool."""

    query: str = Field(
        description="Question or query to search in the indexed content",
        min_length=1,
        max_length=500,
    )
    max_results: int = Field(
        description="Maximum number of relevant documents to return (default: 4)",
        default=4,
        ge=1,
        le=10,
    )


class ScrapeAndIndex(WebScraperBaseTool):
    """Tool for scraping web content and indexing it into a searchable vector store.

    This tool can scrape multiple URLs, process the content into chunks,
    and store it in a vector database for later retrieval and question answering.
    """

    name: str = "web_scraper_scrape_and_index"
    description: str = (
        "Scrape content from one or more web URLs and index them into a vector store for later querying.\n"
        "Use this tool to collect and index web content that you want to reference later.\n"
        "The indexed content can then be queried using the query_indexed_content tool."
    )
    args_schema: Type[BaseModel] = ScrapeAndIndexInput

    def _validate_urls(self, urls: List[str]) -> List[str]:
        """Validate and filter URLs."""
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
        return valid_urls

    async def _arun(
        self,
        urls: List[str],
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        config: RunnableConfig = None,
        **kwargs,
    ) -> str:
        """Scrape URLs and index content into vector store."""
        try:
            # Validate URLs
            valid_urls = self._validate_urls(urls)
            if not valid_urls:
                return "Error: No valid URLs provided. URLs must start with http:// or https://"

            # Get agent context for storage
            context = self.context_from_config(config) if config else None
            agent_id = context.agent.id if context else "default"

            # Load documents from URLs
            logger.info(f"Scraping {len(valid_urls)} URLs...")
            loader = WebBaseLoader(
                web_paths=valid_urls,
                requests_per_second=2,  # Be respectful to servers
                show_progress=True,
            )

            # Configure loader for better content extraction
            loader.requests_kwargs = {
                "verify": True,
                "timeout": 30,
            }

            documents = await asyncio.to_thread(loader.load)

            if not documents:
                return "Error: No content could be extracted from the provided URLs."

            # Split documents into chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                length_function=len,
            )
            split_docs = text_splitter.split_documents(documents)

            if not split_docs:
                return "Error: No content could be processed into chunks."

            # Create embeddings and vector store
            api_key = self.skill_store.get_system_config("openai_api_key")
            embeddings = OpenAIEmbeddings(api_key=api_key)

            # Create vector store
            vector_store = FAISS.from_documents(split_docs, embeddings)

            # Store the vector store for this agent using a temporary directory
            vector_store_key = f"vector_store_{agent_id}"
            metadata_key = f"indexed_urls_{agent_id}"

            # Save vector store to temporary directory and encode to base64
            with tempfile.TemporaryDirectory() as temp_dir:
                vector_store.save_local(temp_dir)

                # Read and encode all files in the temporary directory
                encoded_files = {}
                for filename in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, filename)
                    if os.path.isfile(file_path):
                        with open(file_path, "rb") as f:
                            encoded_files[filename] = base64.b64encode(f.read()).decode(
                                "utf-8"
                            )

            # Store vector store data
            await self.skill_store.save_agent_skill_data(
                agent_id=agent_id,
                skill="web_scraper",
                key=vector_store_key,
                data={
                    "faiss_files": encoded_files,
                    "chunk_size": chunk_size,
                    "chunk_overlap": chunk_overlap,
                },
            )

            # Store metadata about indexed URLs
            existing_metadata = (
                await self.skill_store.get_agent_skill_data(
                    agent_id, "web_scraper", metadata_key
                )
                or {}
            )
            existing_metadata.update(
                {
                    url: {
                        "indexed_at": str(asyncio.get_event_loop().time()),
                        "chunks": len(
                            [
                                doc
                                for doc in split_docs
                                if doc.metadata.get("source") == url
                            ]
                        ),
                    }
                    for url in valid_urls
                }
            )

            await self.skill_store.save_agent_skill_data(
                agent_id=agent_id,
                skill="web_scraper",
                key=metadata_key,
                data=existing_metadata,
            )

            total_chunks = len(split_docs)
            successful_urls = len(valid_urls)

            return (
                f"Successfully scraped and indexed {successful_urls} URLs:\n"
                f"{'• ' + chr(10) + '• '.join(valid_urls)}\n\n"
                f"Total chunks created: {total_chunks}\n"
                f"Chunk size: {chunk_size} characters\n"
                f"Chunk overlap: {chunk_overlap} characters\n\n"
                f"The content is now indexed and can be queried using the query_indexed_content tool."
            )

        except Exception as e:
            logger.error(f"Error in scrape_and_index: {e}")
            return f"Error scraping and indexing URLs: {str(e)}"


class QueryIndexedContent(WebScraperBaseTool):
    """Tool for querying previously indexed web content.

    This tool searches through content that was previously scraped and indexed
    using the scrape_and_index tool to answer questions or find relevant information.
    """

    name: str = "web_scraper_query_indexed_content"
    description: str = (
        "Query previously indexed web content to find relevant information and answer questions.\n"
        "Use this tool to search through content that was previously scraped and indexed.\n"
        "This tool can help answer questions based on the indexed web content."
    )
    args_schema: Type[BaseModel] = QueryIndexInput

    async def _arun(
        self,
        query: str,
        max_results: int = 4,
        config: RunnableConfig = None,
        **kwargs,
    ) -> str:
        """Query the indexed content."""
        try:
            # Get agent context for storage
            context = self.context_from_config(config) if config else None
            agent_id = context.agent.id if context else "default"

            # Retrieve vector store
            vector_store_key = f"vector_store_{agent_id}"
            metadata_key = f"indexed_urls_{agent_id}"

            stored_data = await self.skill_store.get_agent_skill_data(
                agent_id, "web_scraper", vector_store_key
            )
            if not stored_data or "faiss_files" not in stored_data:
                return (
                    "No indexed content found. Please use the scrape_and_index tool first "
                    "to scrape and index some web content before querying."
                )

            # Restore vector store from base64 encoded files
            api_key = self.skill_store.get_system_config("openai_api_key")
            embeddings = OpenAIEmbeddings(api_key=api_key)

            with tempfile.TemporaryDirectory() as temp_dir:
                # Decode and write files to temporary directory
                for filename, encoded_content in stored_data["faiss_files"].items():
                    file_path = os.path.join(temp_dir, filename)
                    with open(file_path, "wb") as f:
                        f.write(base64.b64decode(encoded_content))

                # Load the vector store from the temporary directory
                vector_store = FAISS.load_local(
                    temp_dir,
                    embeddings,
                    allow_dangerous_deserialization=True,  # Safe since we control the serialization
                )

                # Perform similarity search
                relevant_docs = vector_store.similarity_search(query, k=max_results)

            if not relevant_docs:
                return f"No relevant content found for query: '{query}'"

            # Get metadata about indexed URLs
            metadata = (
                await self.skill_store.get_agent_skill_data(
                    agent_id, "web_scraper", metadata_key
                )
                or {}
            )

            # Format response
            response_parts = [
                f"Found {len(relevant_docs)} relevant pieces of content for: '{query}'\n",
                "=" * 50,
            ]

            for i, doc in enumerate(relevant_docs, 1):
                source_url = doc.metadata.get("source", "Unknown source")
                title = doc.metadata.get("title", "No title")

                response_parts.extend(
                    [
                        f"\n{i}. Source: {source_url}",
                        f"   Title: {title}",
                        f"   Content:\n   {doc.page_content[:500]}{'...' if len(doc.page_content) > 500 else ''}",
                        "",
                    ]
                )

            # Add summary of indexed content
            response_parts.extend(
                [
                    "\n" + "=" * 50,
                    f"Total indexed URLs: {len(metadata)}",
                    "Indexed sources:",
                    *[f"• {url}" for url in metadata.keys()],
                ]
            )

            return "\n".join(response_parts)

        except Exception as e:
            logger.error(f"Error in query_indexed_content: {e}")
            return f"Error querying indexed content: {str(e)}"
