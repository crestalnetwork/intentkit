# Firecrawl Skills

The Firecrawl skills provide advanced web scraping and content indexing capabilities using the Firecrawl API. These skills can handle JavaScript-heavy websites, PDFs, and provide automatic content indexing for intelligent querying.

## Skills Overview

### 1. firecrawl_scrape
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

**Use Case:** Use this when you want to refresh/update content from a URL that was previously scraped, ensuring no duplicate or stale content remains.

### 2. firecrawl_crawl
Crawls multiple pages from a website and indexes all content.

**Parameters:**
- `url` (required): The base URL to start crawling
- `include_paths` (optional): URL patterns to include (e.g., ["/docs/*"])
- `exclude_paths` (optional): URL patterns to exclude
- `max_depth` (optional): Maximum crawl depth (default: 2)
- `limit` (optional): Maximum number of pages to crawl (default: 5)
- `index_content` (optional): Whether to index content for querying (default: true)
- `chunk_size` (optional): Size of text chunks for indexing (default: 1000)
- `chunk_overlap` (optional): Overlap between chunks (default: 200)

### 3. firecrawl_query_indexed_content
Queries previously indexed Firecrawl content using semantic search.

**Parameters:**
- `query` (required): The search query
- `limit` (optional): Maximum number of results to return (1-10, default: 4)

### 4. firecrawl_clear_indexed_content
Clears all previously indexed Firecrawl content from the vector store.

**Parameters:**
- `confirm` (required): Must be set to true to confirm the deletion (default: false)

**Note:** This action is permanent and cannot be undone. Use when you want to start fresh with new content.

## API Key Configuration
Set your Firecrawl API key as an environment variable:
```bash
export FIRECRAWL_API_KEY=fc-your-api-key-here
```

## Testing Instructions

### Step 1: Create an Agent with Firecrawl Skills

1. **Create a new agent** via the API or UI with the following skills:
   ```json
   {
     "skills": [
       "firecrawl_scrape",
       "firecrawl_crawl", 
       "firecrawl_query_indexed_content",
       "firecrawl_clear_indexed_content"
     ]
   }
   ```

2. **Note the agent ID** for testing

### Step 2: Test Single Page Scraping

**Test scraping a documentation homepage:**
```
Prompt: "Use firecrawl_scrape to scrape https://docs.joincommonwealth.xyz/ and index the content for future querying"
```

**Expected Result:**
- Content successfully scraped
- Content automatically indexed with metadata
- Confirmation of chunk creation and indexing

### Step 3: Test Content Crawling

**Test crawling multiple pages:**
```
Prompt: "Use firecrawl_crawl to crawl https://docs.joincommonwealth.xyz/ with max_depth=2 and limit=3 to index multiple documentation pages"
```

**Expected Result:**
- Multiple pages crawled and scraped
- Each page indexed separately
- Batch processing confirmation

### Step 4: Test Content Querying

**Test querying indexed content:**
```
Prompt: "Use firecrawl_query_indexed_content to search for 'What is All Street and what is its purpose?' in the indexed content"
```

**Expected Result:**
- Relevant content retrieved from indexed documents
- Results tagged with [Firecrawl Scrape] or [Firecrawl Crawl]
- Source URLs and metadata included

### Step 5: Test Advanced Scraping Options

**Test with specific formatting:**
```
Prompt: "Use firecrawl_scrape to scrape https://docs.joincommonwealth.xyz/all-street-manifesto with formats=['markdown', 'html'] and include_tags=['h1', 'h2', 'p'] and index_content=true"
```

**Expected Result:**
- Content in both markdown and HTML formats
- Only specified HTML tags included
- Content indexed for querying

### Step 6: Test Multiple Queries

**Test different query types:**
```
Prompt: "Use firecrawl_query_indexed_content to search for 'democratize finance' in the indexed content"
```

**Expected Result:**
- Relevant content retrieved from Firecrawl's independent vector store
- Results tagged with [Firecrawl Scrape] or [Firecrawl Crawl]
- Source URLs and metadata included

### Step 7: Test Clear Indexed Content

**Test clearing all indexed content:**
```
Prompt: "Use firecrawl_clear_indexed_content with confirm=true to clear all indexed content"
```

**Expected Result:**
- All indexed content removed from vector store
- Confirmation message displayed
- Subsequent queries return no results

### Step 8: Test Re-indexing After Clear

**Test that content can be re-indexed after clearing:**
```
Prompt: "Use firecrawl_scrape to scrape https://example.com and index the content"
```

**Expected Result:**
- Content successfully scraped and indexed
- Fresh vector store created
- Content available for querying again

## Common Use Cases

### Documentation Indexing
```
1. Scrape main documentation page
2. Crawl related documentation sections  
3. Use scrape again to update changed pages (replaces old content)
4. Query for specific technical information
```

### Competitive Analysis
```
1. Scrape competitor websites
2. Index product information and features
3. Query for specific comparisons
```

### Research and Knowledge Base
```
1. Crawl research papers or articles
2. Index academic or technical content
3. Query for specific concepts or methodologies
```

## Troubleshooting

### Common Issues

1. **API Key Not Found**
   - Ensure `FIRECRAWL_API_KEY` environment variable is set
   - Restart the IntentKit server after setting the key

2. **Scraping Failures**
   - Check if the URL is accessible
   - Verify Firecrawl API quota and limits
   - Some websites may block scraping

3. **Indexing Errors**
   - Ensure OpenAI API key is configured for embeddings
   - Check if content is too large for processing
   - Verify vector store permissions

4. **Query Returns No Results**
   - Ensure content was successfully indexed
   - Try broader or different search terms
   - Check if vector store contains data

## Features and Benefits

- **JavaScript Rendering**: Handles SPAs and dynamic content
- **PDF Support**: Can scrape and index PDF documents
- **Intelligent Chunking**: Optimized text splitting for better search
- **Independent Storage**: Uses its own dedicated vector store for Firecrawl content
- **Content Replacement**: Replace mode prevents duplicate/stale content
- **Metadata Rich**: Includes source URLs, timestamps, and content types
- **Semantic Search**: Uses OpenAI embeddings for intelligent querying
- **Batch Processing**: Efficient handling of multiple pages
- **Content Filtering**: Flexible include/exclude options for targeted scraping