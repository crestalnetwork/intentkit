# AIXBT Skill

This skill provides access to cryptocurrency project data and analytics through the AIXBT API.

## Features

- Search for cryptocurrency projects by name, ticker, or blockchain
- Get detailed analysis and information about crypto projects
- Filter projects by minimum score
- View recent project updates and developments
- Access project contact information and social media handles
- Special "alpha" trigger for direct access to crypto research

## Available Skills

### aixbt_projects

Searches for cryptocurrency projects and retrieves detailed information about them.

#### Special Trigger

This skill has a special trigger word: **"alpha"**

When a user mentions the word "alpha" anywhere in their message, the AIXBT skill will be automatically triggered. This works with phrases like:
- "Show me some alpha"
- "What's the latest alpha on crypto?"
- "Give me alpha on Bitcoin"
- "I'm looking for alpha in DeFi projects"
- Any other message containing the word "alpha"

This gives users a convenient way to access crypto research data just by mentioning "alpha" in their questions or requests.

#### Parameters

| Name | Type | Description | Required | Default |
|------|------|-------------|----------|---------|
| limit | integer | Number of projects to return (max 50) | No | 10 |
| name | string | Filter projects by name (case-insensitive regex match) | No | null |
| ticker | string | Filter projects by ticker symbol (case-insensitive match) | No | null |
| xHandle | string | Filter projects by X/Twitter handle | No | null |
| minScore | number | Minimum score threshold | No | null |
| chain | string | Filter projects by blockchain | No | null |

## Example Usage

### "Alpha" Trigger Examples

**User:** "Show me some alpha"

**Agent:** *Uses the aixbt_projects skill to search for trending cryptocurrency projects and provides comprehensive information about them.*

**User:** "What's the latest alpha on Bitcoin?"

**Agent:** *Uses the aixbt_projects skill to search specifically for Bitcoin and provides detailed information.*

### Standard Query

When a user asks about a cryptocurrency project:

**User:** "Tell me about the Bitcoin project"

**Agent:** *Uses the aixbt_projects skill to search for "bitcoin" and provides information including:*
- Project score and analysis
- Recent project updates
- Social media information
- Blockchain and token details

## Links

- [AIXBT Website](https://aixbt.tech/)
- [API Documentation](https://api.aixbt.tech/v1/docs/) 