# Tavily Skills

This skill package enables agents to search the web and extract content from web pages using the [Tavily](https://tavily.com/) API.

## Overview

The Tavily skills allow agents to:
- Search the internet for current information
- Retrieve relevant search results with snippets and URLs
- Extract full content from specific web pages
- Find answers to questions that may not be in the agent's training data
- Access real-time information and news

## Available Skills

### 1. Tavily Search
Allows agents to search the web for current information and retrieve relevant results.

### 2. Tavily Extract
Allows agents to extract full content from specific URLs, including text and optionally images.

## Configuration

To enable these skills, add the following to your agent configuration:

```yaml
skills:
  tavily:
    enabled: true
    api_key: "your-tavily-api-key"
    states:
      tavily_search: public  # or "private" or "disabled"
      tavily_extract: public  # or "private" or "disabled"
```

### Configuration Options

- `enabled`: Whether the skills are enabled (true/false)
- `api_key`: Your Tavily API key
- `states.tavily_search`: The state of the Tavily search skill
  - `public`: Available to agent owner and all users
  - `private`: Available only to the agent owner
  - `disabled`: Not available to anyone
- `states.tavily_extract`: The state of the Tavily extract skill
  - `public`: Available to agent owner and all users
  - `private`: Available only to the agent owner
  - `disabled`: Not available to anyone

## Usage Examples

### Tavily Search

The agent will automatically use Tavily search when:
- A user asks for current information or news
- The agent needs to verify facts or find up-to-date information
- A query seeks information that may not be in the agent's training data

**Example Interaction:**

**User**: "What's the current price of Bitcoin?"

**Agent**: *Uses Tavily search to find current cryptocurrency prices*

### Tavily Extract

The agent will automatically use Tavily extract when:
- A user wants to extract or scrape content from a specific URL
- The agent needs to analyze the full content of a web page
- A query requires detailed information from a particular website

**Example Interaction:**

**User**: "Can you extract the content from https://en.wikipedia.org/wiki/Artificial_intelligence"

**Agent**: *Uses Tavily extract to retrieve the full content from the Wikipedia page*

## API Requirements

These skills require a valid Tavily API key. You can sign up for one at [tavily.com](https://tavily.com/).

## Limitations

- Search results are limited to a maximum of 10 items per query
- Extract functionality may not work on all websites due to access restrictions
- The quality of results depends on the Tavily API
- Rate limits may apply based on your Tavily API plan 