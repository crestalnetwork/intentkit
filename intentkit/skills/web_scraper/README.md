# Web Scraper & Content Indexing Skills

Intelligent web scraping and content indexing using LangChain's WebBaseLoader with vector search capabilities.

## Skills

### 🔍 `scrape_and_index`
Scrape content from URLs and index into a searchable vector store with configurable chunking and persistent storage.

### 🔎 `query_indexed_content`
Search indexed content using semantic similarity to answer questions and retrieve relevant information.

## Key Features

- **Multi-URL Support**: Scrape up to 10 URLs simultaneously
- **Smart Chunking**: Configurable text splitting (100-4000 chars) with overlap
- **Vector Search**: FAISS + OpenAI embeddings for semantic retrieval
- **Agent Storage**: Persistent, per-agent content indexing
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

### 3. Content Querying

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
- `langchain-community` - WebBaseLoader
- `langchain-openai` - Embeddings
- `langchain-text-splitters` - Document chunking  
- `faiss-cpu` - Vector storage
- `beautifulsoup4` - HTML parsing