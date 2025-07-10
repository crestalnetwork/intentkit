# HTTP Client Skills

This skill category provides HTTP client functionality for making web requests using the httpx async client library.

## Available Skills

### http_get
Make HTTP GET requests to fetch data from web APIs and websites.

**Parameters:**
- `url` (string, required): The URL to send the GET request to
- `headers` (dict, optional): Custom headers to include in the request
- `params` (dict, optional): Query parameters to include in the request
- `timeout` (float, optional): Request timeout in seconds (default: 30)

**Example usage:**
```
Fetch data from https://api.example.com/users with timeout of 10 seconds
```

### http_post
Make HTTP POST requests to send data to web APIs and submit forms.

**Parameters:**
- `url` (string, required): The URL to send the POST request to
- `data` (dict or string, optional): The data to send in the request body
- `headers` (dict, optional): Custom headers to include in the request
- `params` (dict, optional): Query parameters to include in the request
- `timeout` (float, optional): Request timeout in seconds (default: 30)

**Example usage:**
```
Send a POST request to https://api.example.com/users with JSON data {"name": "John", "email": "john@example.com"}
```

### http_put
Make HTTP PUT requests to update or replace data on web APIs.

**Parameters:**
- `url` (string, required): The URL to send the PUT request to
- `data` (dict or string, optional): The data to send in the request body
- `headers` (dict, optional): Custom headers to include in the request
- `params` (dict, optional): Query parameters to include in the request
- `timeout` (float, optional): Request timeout in seconds (default: 30)

**Example usage:**
```
Update user data at https://api.example.com/users/123 with {"name": "Jane Doe"}
```

## Features

- **Async Support**: All HTTP operations are asynchronous using httpx
- **Automatic JSON Handling**: Dictionary data is automatically sent as JSON with proper Content-Type headers
- **Error Handling**: Comprehensive error handling for timeouts, HTTP errors, and connection issues
- **Flexible Data Types**: Support for both JSON (dict) and raw string data in POST/PUT requests
- **Custom Headers**: Support for custom headers in all request types
- **Query Parameters**: Support for URL query parameters
- **Configurable Timeouts**: Customizable request timeouts

## Configuration

Each skill can be configured with one of three states:
- `disabled`: Skill is not available
- `public`: Available to both agent owner and all users
- `private`: Available only to the agent owner

## Natural Language Usage

These skills are designed to work seamlessly with natural language instructions:

- "Get the weather data from the API"
- "Send a POST request to create a new user"
- "Update the user profile using PUT request"
- "Fetch the latest news from the RSS feed"
- "Submit the form data to the webhook"

The AI agent will automatically select the appropriate HTTP method and construct the proper request based on your natural language description.