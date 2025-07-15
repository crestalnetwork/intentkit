# IntentKit

<div align="center">
  <img src="docs/images/intentkit_banner.png" alt="IntentKit by Crestal" width="100%" />
</div>
<br>

IntentKit is an autonomous agent framework that enables the creation and management of AI agents with various capabilities including blockchain interaction, social media management, and custom skill integration.

## Package Manager Migration Warning

We just migrated to uv from poetry.
You need to delete the .venv folder and run `uv sync` to create a new virtual environment. (one time)
```bash
rm -rf .venv
uv sync
```

## Features

- 🤖 Multiple Agent Support
- 🔄 Autonomous Agent Management
- 🔗 Blockchain Integration (EVM chains first)
- 🐦 Social Media Integration (Twitter, Telegram, and more)
- 🛠️ Extensible Skill System
- 🔌 MCP (WIP)

## Architecture

```
                                                                                    
                                 Entrypoints                                        
                       │                             │                              
                       │   Twitter/Telegram & more   │                              
                       └──────────────┬──────────────┘                              
                                      │                                             
  Storage:  ────┐                     │                      ┌──── Skills:          
                │                     │                      │                      
  Agent Config  │     ┌───────────────▼────────────────┐     │  Chain Integration   
                │     │                                │     │                      
  Credentials   │     │                                │     │  Wallet Management   
                │     │           The Agent            │     │                      
  Personality   │     │                                │     │  On-Chain Actions    
                │     │                                │     │                      
  Memory        │     │      Powered by LangGraph      │     │  Internet Search     
                │     │                                │     │                      
  Skill State   │     └────────────────────────────────┘     │  Image Processing    
            ────┘                                            └────                  
                                                                                    
                                                                More and More...    
                         ┌──────────────────────────┐                               
                         │                          │                               
                         │  Agent Config & Memory   │                               
                         │                          │                               
                         └──────────────────────────┘                               
                                                                                    
```

The architecture is a simplified view, and more details can be found in the [Architecture](docs/architecture.md) section.

## Development

Read [Development Guide](DEVELOPMENT.md) to get started with your setup.

## Documentation

Check out [Documentation](docs/) before you start.

## Project Structure

The project is divided into the core package and the application:

- **[intentkit/](intentkit/)**: The IntentKit package (published as a pip package)
  - [abstracts/](intentkit/abstracts/): Abstract classes and interfaces for core and skills
  - [clients/](intentkit/clients/): Clients for external services
  - [config/](intentkit/config/): System level configurations
  - [core/](intentkit/core/): Core agent system, driven by LangGraph
  - [models/](intentkit/models/): Entity models using Pydantic and SQLAlchemy
  - [skills/](intentkit/skills/): Extensible skills system, based on LangChain tools
  - [utils/](intentkit/utils/): Utility functions

- **[app/](app/)**: The IntentKit app (API server, autonomous runner, and background scheduler)
  - [admin/](app/admin/): Admin APIs, agent generators, and related functionality
  - [entrypoints/](app/entrypoints/): Entrypoints for interacting with agents (web, Telegram, Twitter, etc.)
  - [services/](app/services/): Service implementations for Telegram, Twitter, etc.
  - [api.py](app/api.py): REST API server
  - [autonomous.py](app/autonomous.py): Autonomous agent runner
  - [checker.py](app/checker.py): Health and credit checking logic
  - [readonly.py](app/readonly.py): Readonly entrypoint
  - [scheduler.py](app/scheduler.py): Background task scheduler
  - [singleton.py](app/singleton.py): Singleton agent manager
  - [telegram.py](app/telegram.py): Telegram integration
  - [twitter.py](app/twitter.py): Twitter integration

- [docs/](docs/): Documentation
- [scripts/](scripts/): Operation and temporary scripts for management and migrations

## Agent API

IntentKit provides a comprehensive REST API for programmatic access to your agents. Build applications, integrate with existing systems, or create custom interfaces using our Agent API.

**Get Started:** [Agent API Documentation](docs/agent_api.md)

## Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) before submitting a pull request.

### Contribute Skills

First check [Wishlist](docs/contributing/wishlist.md) for active requests.

Once you are ready to start, see [Skill Development Guide](docs/contributing/skills.md) for more information.

### Developer Chat

Join our [Discord](https://discord.com/invite/crestal), open a support ticket to apply for an intentkit dev role.

We have a discussion channel there for you to join up with the rest of the developers.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
