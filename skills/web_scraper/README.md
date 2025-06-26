# Web Scraper & Content Indexing Skills

Intelligent web scraping and content indexing using LangChain's WebBaseLoader with vector search capabilities.

## Skills

### 🔍 `scrape_and_index`
Scrape content from URLs and index into a searchable vector store with configurable chunking and persistent storage.

### 🔎 `query_indexed_content`
Search indexed content using semantic similarity to answer questions and retrieve relevant information.

### `website_indexer`
Index entire websites by discovering and scraping all pages using sitemaps. Automatically finds sitemaps from robots.txt, extracts all URLs, and comprehensively indexes website content.

### `document_indexer`
Import and index document content directly to the vector database. Perfect for adding content from Google Docs, Notion pages, PDFs, or any other document sources by copy-pasting.

## Key Features

- **Multi-URL Support**: Scrape up to 10 URLs simultaneously 
- **Sitemap Discovery**: Automatic sitemap detection from robots.txt with common patterns
- **Direct Text Input**: Add content directly without web scraping
- **Smart Chunking**: Configurable text splitting (100-4000 chars) with overlap
- **Vector Search**: FAISS + OpenAI embeddings for semantic retrieval
- **Agent Storage**: Persistent, per-agent content indexing
- **Content Filtering**: Include/exclude URL patterns for targeted scraping
- **Tagging System**: Organize content with custom tags
- **Rate Limiting**: Respectful scraping (0.1-10 req/sec)

## Testing Examples

### 1. Basic Scraping & Indexing

**Agent Prompt:**
```
Please scrape and index this URL: https://docs.crestal.network/introduction
```

**Expected Response:**
- Confirmation of successful scraping
- Number of URLs processed and chunks created
- Storage confirmation message

### 2. Custom Chunking

**Agent Prompt:**
```
Scrape and index https://docs.crestal.network/introduction with chunk size 500 and overlap 100.
```

### 3. Complete Website Indexing

**Agent Prompt:**
```
Index the entire documentation site at https://docs.crestal.network using its sitemap. Include only pages with '/docs/' and '/guides/' in the URL, exclude '/admin/' pages, and limit to 50 URLs.
```

### 4. Document Content Import

**Agent Prompt:**
```
I'm going to paste some content from my Google Doc. Please add it to the knowledge base:

Title: "Meeting Notes - Q4 Strategy"
Source: "Google Docs"
Tags: "meeting, strategy, q4, planning"

[Paste your document content here...]
```

### 5. Content Querying

**Agent Prompt (after indexing):**
```
Based on the indexed documentation, what are the main items in it?
```


## Testing Workflow

1. **Setup**: Configure the skill in your agent
2. **Index Content**: Use `scrape_and_index` with test URLs
3. **Query Content**: Use `query_indexed_content` with questions
4. **Verify**: Check responses include source attribution and relevant content

## API Testing

```bash
# Test scraping via API
curl -X POST "http://localhost:8000/agents/your-agent-id/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Scrape and index https://docs.crestal.network/introduction"
  }'

# Test querying via API  
curl -X POST "http://localhost:8000/agents/your-agent-id/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What information did you find?"
  }'
```

## Dependencies

Required packages (add to `pyproject.toml` if missing):
- `langchain-community` - WebBaseLoader and document processing
- `langchain-openai` - Embeddings
- `langchain-text-splitters` - Document chunking  
- `faiss-cpu` - Vector storage
- `beautifulsoup4` - HTML parsing
- `httpx` - Async HTTP client for sitemap discovery