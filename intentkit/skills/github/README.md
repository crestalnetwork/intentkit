# GitHub Skill

This skill enables agents to search GitHub for repositories, users, and code using GitHub's public API endpoints.

## Features

- Search GitHub repositories by name, description, or topics
- Search GitHub users by username or real name
- Search code snippets across GitHub repositories
- No authentication required (uses public API endpoints)
- Rate limit aware (respects GitHub's public API limits)

## Configuration

Add the GitHub skill to your agent's configuration:

```yaml
skills:
  github:
    states:
      github_search: public  # or private if you want to restrict access
```

## Usage Examples

The agent can use the GitHub skill to answer questions like:

- "Find repositories about blockchain development"
- "Search for users who work on web3 projects"
- "Find code examples of smart contracts in Solidity"
- "Show me popular Python machine learning repositories"
- "Find developers who contribute to Ethereum"

## Rate Limits

The skill uses GitHub's public API which has the following rate limits:
- 60 requests per hour per IP address
- No authentication required
- Results are limited to public repositories and users

## Implementation Details

The skill uses the following GitHub API endpoints:
- `/search/repositories` - For searching repositories
- `/search/users` - For searching users
- `/search/code` - For searching code

Each search result includes:
- For repositories: name, description, language, stars count, and URL
- For users: username, name, bio, and profile URL
- For code: repository name, file path, and URL

## Error Handling

The skill handles various error cases:
- API rate limits
- Network errors
- Invalid queries
- No results found

## Logging

All operations are logged with the prefix `github_search.py:` for easy debugging and monitoring. 