# CARV API Skills: Your Gateway to Blockchain & Crypto Data

This collection of tools helps your AI agent connect to the [CARV API](https://docs.carv.io/d.a.t.a.-ai-framework/api-documentation) to get useful information about cryptocurrencies, blockchain activity, and the latest news in the space. Think of them as special abilities your agent can use!

**Icon:** ![](skills/carv/carv.webp)
**Tags:** AI, Data, Information, Analytics, Market Data

## What Can Your Agent Do With These Skills?

Here are the tools available:

### 1. Fetch News (`FetchNewsTool`)

*   **What it does:** Gets the latest news articles from CARV.
*   **What you need to provide:** Nothing! Just ask for the news.
*   **Example Agent Interaction:** "Hey agent, what's the latest crypto news?"
*   **What it returns:** A list of news items, each with a:
    *   `title`: The headline of the news.
    *   `url`: A link to the full article.
    *   `card_text`: A short summary.
    *   *Example output snippet:*
      ```json
      {
        "infos": [
          {
            "title": "Big Blockchain Conference Announced",
            "url": "https://example.com/news/conference",
            "card_text": "A major conference focusing on blockchain technology will be held next month..."
          }
          // ... more news items
        ]
      }
      ```

### 2. On-Chain Query (`OnchainQueryTool`)

*   **What it does:** Lets you ask questions in plain English about what's happening on blockchains like Ethereum, Base, Bitcoin, or Solana. CARV figures out how to get the answer from the blockchain data.
*   **What you need to provide:**
    *   `question` (text): Your question about blockchain data (e.g., "What was the biggest Bitcoin transaction yesterday?").
    *   `chain` (text): The blockchain you're interested in (e.g., "ethereum", "bitcoin").
*   **Example Agent Interaction:** "Agent, show me the top 5 most active wallets on Solana in the last week."
*   **What it returns:** A structured table of data that answers your question. If your question involves token amounts (like ETH or BTC), the tool automatically converts them into easy-to-read numbers (e.g., "1.5 ETH" instead of a very long number).
    *   *Example output snippet (conceptual for "biggest ETH transaction last 24h"):*
      ```json
      {
        "data": {
          "column_infos": ["transaction_hash", "from_address", "to_address", "value", "timestamp"],
          "rows": [
            {
              "items": ["0xabc...", "0x123...", "0x456...", "1500.75 ETH", "2023-10-27T10:30:00Z"]
            }
            // ... potentially more rows if your question implies multiple results
          ]
        },
        "query": "SELECT ... FROM ethereum.transactions ... ORDER BY value DESC LIMIT 1" // The SQL CARV generated
      }
      ```
    *   If something goes wrong (e.g., you ask about an unsupported blockchain), it will return an error message.

### 3. Token Information and Price (`TokenInfoAndPriceTool`)

*   **What it does:** Gets details about a specific cryptocurrency (like its name, symbol, what platform it's on) and its current price in USD.
*   **What you need to provide:**
    *   `ticker` (text): The token's symbol (e.g., "BTC", "ETH", "SOL").
    *   `token_name` (text): The full name of the token (e.g., "Bitcoin", "Ethereum").
    *   `amount` (number, optional): If you want to know the value of a specific amount of the token, include this (e.g., if you provide `amount: 2.5` and `ticker: "BTC"`, it will tell you what 2.5 BTC is worth).
*   **Example Agent Interaction:** "Agent, what's the current price of Ethereum? Also, what would 5 ETH be worth?"
*   **What it returns:** Information about the token, including its price. If you provided an amount, it also tells you the total value.
    *   *Example output snippet (for `ticker: "ETH"`, `token_name: "Ethereum"`, `amount: 5`):*
      ```json
      {
        "name": "Ethereum",
        "symbol": "ETH",
        "price": 2000.50, // Current price of 1 ETH in USD
        "platform": {"id": "ethereum", "name": "Ethereum"},
        "categories": ["Smart Contract Platform"],
        // ... other details
        "additional_info": "5 ETH is worth $10002.50" // Calculated if amount was given
      }
      ```
    *   If it can't find the token or its price, it will return an error.

## How to Get Started (For Developers)

These tools are designed to be integrated into AI agent systems.

*   **Configuration:** You'll need to set up how these tools access the CARV API. This usually involves:
    *   Enabling the CARV skills.
    *   Deciding if the tools can be used by everyone or just the agent owner.
    *   Providing a CARV API key. This key can either be supplied directly in your agent's settings or managed by the platform your agent runs on.
    *   Details on how to configure this are in a `schema.json` file within the `skills/carv/` directory.

*   **Using the Tools:** Your agent's code will call these tools, providing the necessary inputs (like the ticker for `TokenInfoAndPriceTool`). The tools will then contact the CARV API and return the information.

These CARV skills make it easy for your AI agent to become knowledgeable about the crypto world!