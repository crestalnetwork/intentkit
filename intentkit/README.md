# IntentKit

IntentKit is a powerful intent-based AI agent platform that enables developers to build sophisticated AI agents with blockchain and cryptocurrency capabilities.

## Features

- **Intent-based Architecture**: Build agents that understand and execute user intents
- **Blockchain Integration**: Native support for multiple blockchain networks
- **Cryptocurrency Operations**: Built-in tools for DeFi, trading, and token operations
- **Extensible Skills System**: Modular skill system with 30+ pre-built skills
- **Multi-platform Support**: Telegram, Twitter, Slack, and API integrations
- **Advanced AI Capabilities**: Powered by LangChain and LangGraph

## Installation

```bash
pip install intentkit
```

## Development

To build the package locally:

```bash
# Build both source and wheel distributions
uv build

# Build only wheel
uv build --wheel

# Build only source distribution
uv build --sdist
```

To publish to PyPI:

```bash
# Build and publish to PyPI
uv build
uv publish

# Publish to Test PyPI
uv publish --publish-url https://test.pypi.org/legacy/
```

> **Note**: This package uses `hatchling` as the build backend with `uv` for dependency management and publishing.

## Quick Start

```python
from intentkit.core.agent import Agent
from intentkit.config.config import Config

# Initialize configuration
config = Config()

# Create an agent
agent = Agent(config=config)

# Your agent is ready to use!
```

## Skills

IntentKit comes with 30+ pre-built skills including:

- **DeFi**: Uniswap, 1inch, Enso, LiFi
- **Data**: DexScreener, CoinGecko, DefiLlama, CryptoCompare
- **Social**: Twitter, Telegram, Slack
- **Blockchain**: CDP, Moralis, various wallet integrations
- **AI**: OpenAI, Heurist, Venice AI
- **And many more...**

## Documentation

For detailed documentation, examples, and guides, visit our [documentation](https://github.com/crestal-network/intentkit/tree/main/docs).

## Contributing

We welcome contributions! Please see our [Contributing Guide](https://github.com/crestal-network/intentkit/blob/main/CONTRIBUTING.md) for details.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

For support, please open an issue on our [GitHub repository](https://github.com/crestal-network/intentkit/issues).