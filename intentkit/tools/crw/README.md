# fastCRW Tools

The fastCRW tools provide web scraping and content indexing using [fastCRW](https://fastcrw.com),
a Firecrawl-compatible web data engine that ships as a single binary. Run it
self-hosted (free, open core) or against the managed cloud. These tools mirror
the Firecrawl provider and are additive — both providers can be enabled side by
side.

## Tools Overview

### 1. crw_scrape
Scrapes a single webpage and REPLACES any existing indexed content for that URL, preventing duplicates.

**Parameters:**
- `url` (required): The URL to scrape
- `formats` (optional): Output formats - markdown, html, rawHtml, screenshot, links, json (default: ["markdown"])
- `only_main_content` (optional): Extract only main content (default: true)
- `include_tags` (optional): HTML tags to include (e.g., ["h1", "h2", "p"])
- `exclude_tags` (optional): HTML tags to exclude
- `wait_for` (optional): Wait time in milliseconds before scraping
- `timeout` (optional): Maximum timeout in milliseconds (default: 30000)
- `index_content` (optional): Whether to index content for querying (default: true)
- `chunk_size` (optional): Size of text chunks for indexing (default: 1000)
- `chunk_overlap` (optional): Overlap between chunks (default: 200)

### 2. crw_crawl
Crawls multiple pages from a website and indexes all content.

**Parameters:**
- `url` (required): The base URL to start crawling
- `limit` (optional): Maximum number of pages to crawl (default: 10)
- `include_paths` (optional): URL patterns to include (e.g., ["/docs/*"])
- `exclude_paths` (optional): URL patterns to exclude
- `max_depth` (optional): Maximum crawl depth
- `index_content` (optional): Whether to index content for querying (default: true)
- `chunk_size` (optional): Size of text chunks for indexing (default: 1000)
- `chunk_overlap` (optional): Overlap between chunks (default: 200)

### 3. crw_query_indexed_content
Queries previously indexed fastCRW content using semantic search.

**Parameters:**
- `query` (required): The search query
- `max_results` (optional): Maximum number of results to return (1-10, default: 4)

### 4. crw_clear_indexed_content
Clears all previously indexed fastCRW content from the vector store.

**Parameters:**
- `confirm` (required): Must be set to true to confirm the deletion (default: false)

**Note:** This action is permanent and cannot be undone.

## Configuration

fastCRW is Firecrawl-compatible; the integration defaults to the managed cloud
and lets you override the base URL for a self-hosted server.

```bash
# Managed cloud (default base URL https://fastcrw.com/api)
export CRW_API_KEY=your-api-key-here

# Self-hosted server (auth optional; CRW_API_KEY may be omitted)
export CRW_API_URL=http://localhost:3000
```

- `CRW_API_KEY` — Bearer token. Optional for self-hosted instances that run without auth.
- `CRW_API_URL` — Base URL, default `https://fastcrw.com/api`. Set this to point at a self-hosted server.

Content indexing uses OpenAI embeddings, so `OPENAI_API_KEY` must also be configured.

## Features and Benefits

- **Firecrawl-compatible**: Same REST surface and data shapes as Firecrawl.
- **Single binary**: Self-host the open core for free, or use the managed cloud.
- **JavaScript Rendering**: Handles SPAs and dynamic content.
- **Intelligent Chunking**: Optimized text splitting for better search.
- **Content Replacement**: Replace mode prevents duplicate/stale content on re-scrape.
- **Semantic Search**: Uses OpenAI embeddings for intelligent querying.
