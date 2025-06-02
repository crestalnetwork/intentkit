# Agent Generation Logging

## What it does

Tracks everything when agents get created. Records prompts, token usage, how long it takes, and if it works or fails.

## What gets tracked

- **Requests**: Every time someone asks for an agent
- **Tokens**: How much the OpenAI API costs  
- **Performance**: Time taken, retries, success rates
- **Errors**: What went wrong and why
- **Updates**: New agents and changes to old ones
- **History**: Full record per user

## Database table

```sql
CREATE TABLE agent_generation_logs (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR,
    prompt TEXT NOT NULL,
    existing_agent_id VARCHAR,
    is_update BOOLEAN DEFAULT FALSE,
    generated_agent_schema JSONB,
    identified_skills JSONB,
    openai_model VARCHAR,
    total_tokens INTEGER DEFAULT 0,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    input_tokens_details JSONB,
    completion_tokens_details JSONB,
    generation_time_ms INTEGER,
    retry_count INTEGER DEFAULT 0,
    validation_errors JSONB,
    success BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);
```

## How it works

### API endpoint
```python
@router.post("/generate")
async def generate_agent(request: AgentGenerateRequest):
    # logging happens automatically
    agent_schema, identified_skills = await generate_validated_agent_schema(
        prompt=request.prompt,
        user_id=request.user_id,
        existing_agent=request.existing_agent,
    )
    return agent_schema
```

### Main function
```python
async def generate_validated_agent(prompt, user_id=None, existing_agent=None):
    # create log entry
    log_data = AgentGenerationLogCreate(
        user_id=user_id, prompt=prompt, 
        existing_agent_id=existing_agent.id if existing_agent else None,
        is_update=existing_agent is not None
    )
    generation_log = await AgentGenerationLog.create(session, log_data)
    
    # track tokens while generating
    # ... generation happens here ...
    
    # update with results
    await generation_log.update_completion(
        session=session,
        generated_agent_schema=schema,
        identified_skills=list(identified_skills),
        total_tokens=total_tokens_used,
        success=True
    )
```

### Token counting
```python
def _extract_token_usage(response) -> Dict[str, Any]:
    usage_info = {"total_tokens": 0, "input_tokens": 0, "output_tokens": 0}
    if hasattr(response, "usage") and response.usage:
        usage = response.usage
        usage_info["total_tokens"] = getattr(usage, "total_tokens", 0)
        usage_info["input_tokens"] = getattr(usage, "prompt_tokens", 0)
        usage_info["output_tokens"] = getattr(usage, "completion_tokens", 0)
    return usage_info
```

## Data models

### Creating logs
```python
class AgentGenerationLogCreate(BaseModel):
    user_id: Optional[str] = None
    prompt: str
    existing_agent_id: Optional[str] = None
    is_update: bool = False
```

### Main log model
```python
class AgentGenerationLog(BaseModel):
    # basic operations
    @classmethod
    async def create(cls, session, log_data) -> "AgentGenerationLog"
    async def update_completion(self, session, **kwargs) -> None
    @classmethod
    async def get_by_id(cls, session, log_id) -> Optional["AgentGenerationLog"]
    @classmethod 
    async def get_by_user(cls, session, user_id, limit=50) -> List["AgentGenerationLog"]
```

## Example logs

### When it works
```json
{
    "id": "log_abc123",
    "user_id": "user_456", 
    "prompt": "Create a Twitter bot that posts crypto analysis",
    "is_update": false,
    "generated_agent_schema": {
        "name": "CryptoAnalysisBot",
        "skills": {"twitter": {"enabled": true}, "web_search": {"enabled": true}}
    },
    "identified_skills": ["twitter", "web_search"],
    "total_tokens": 1250,
    "generation_time_ms": 2500,
    "retry_count": 0,
    "success": true
}
```

### When it fails
```json
{
    "id": "log_def789",
    "prompt": "Create an invalid agent",
    "total_tokens": 500,
    "retry_count": 3,
    "validation_errors": {"errors": ["Schema error: Invalid model", "Missing required fields"]},
    "success": false,
    "error_message": "Failed to generate valid agent schema after 3 attempts"
}
```

## Useful queries

### Token usage by user
```sql
SELECT user_id, COUNT(*) as generations, SUM(total_tokens) as tokens_used,
       SUM(CASE WHEN success THEN 1 ELSE 0 END) as successful
FROM agent_generation_logs 
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY user_id ORDER BY tokens_used DESC;
```

### Performance stats
```sql
SELECT DATE(created_at) as date, COUNT(*) as requests,
       AVG(generation_time_ms) as avg_time, AVG(retry_count) as avg_retries,
       AVG(CASE WHEN success THEN 1.0 ELSE 0.0 END) as success_rate
FROM agent_generation_logs 
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at);
```

## Using the API

### Create a log
```python
async with get_session() as session:
    log_data = AgentGenerationLogCreate(user_id="user_123", prompt="Create assistant")
    log = await AgentGenerationLog.create(session, log_data)
```

### Update with results
```python
async with get_session() as session:
    log = await AgentGenerationLog.get_by_id(session, log_id)
    await log.update_completion(session=session, success=True, total_tokens=tokens)
```

### Get user history
```python
async with get_session() as session:
    logs = await AgentGenerationLog.get_by_user(session, user_id, limit=20)
```

## Why this helps

- **Cost tracking**: See how much OpenAI API costs per user
- **Finding problems**: Spot slow parts and things that break  
- **Debugging**: See exactly what went wrong and why
- **User patterns**: Learn what people want to build
- **Compliance**: Keep records for audits
- **Rate limits**: Know when to slow down API calls

## Setup

No extra setup needed. Just call `generate_validated_agent_schema()` and everything gets logged automatically. Token usage and errors get tracked without any extra code. 