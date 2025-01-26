# IntentKit

IntentKit is an autonomous agent framework that enables the creation and management of AI agents with various capabilities including blockchain interactions, social media management, and custom skill integration.

## Alpha Warning

This project is currently in alpha stage and is not recommended for production use.

## Features

- 🤖 Multiple Agent Support
- 🔄 Autonomous Agent Management
- 🔗 Blockchain Integration (EVM for now, will add more)
- 🐦 Social Media Integration (Twitter, Telegram for now, will add more)
- 🛠️ Extensible Skill System
- 🔌 Extensible Plugin System (WIP)

## Architecture

```
                                                                                                       
                                 Entrypoints                                                           
                       │                             │                                                 
                       │   Twitter/Telegram & more   │                                                 
                       └──────────────┬──────────────┘                                                 
                                      │                                                                
  Storage:  ────┐                     │                      ┌──── Skills:                             
                │                     │                      │                                         
  Agent Config  │     ┌───────────────▼────────────────┐     │  Chain Integration (EVM,solana,etc...)  
                │     │                                │     │                                         
  Credentials   │     │                                │     │  Wallet Management                      
                │     │           The  Agent           │     │                                         
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

## Quick Start

### Docker (Recommended)
1. Create a new directory and navigate into it:
```bash
mkdir intentkit && cd intentkit
```

2. Download the required files:
```bash
# Download docker-compose.yml
curl -O https://raw.githubusercontent.com/crestalnetwork/intentkit/main/docker-compose.yml

# Download example environment file
curl -O https://raw.githubusercontent.com/crestalnetwork/intentkit/main/example.env
```

3. Set up environment:
```bash
# Rename example.env to .env
mv example.env .env

# Edit .env file and add your configuration
# Make sure to set OPENAI_API_KEY
```

4. Start the services:
```bash
docker compose up
```

5. Create your first Agent:
```bash
curl -X POST http://127.0.0.1:8000/agents \
     -H "Content-Type: application/json" \
     -d '{
         "id": "admin",
         "name": "Admin",
         "prompt": "You are an autonomous AI agent. Respond to user queries."
     }'
```
There are many fields that can control the agent's behavior, we have provided a [helper shell](docs/create_agent.sh) for you.

6. Try it out:
```bash
curl "http://127.0.0.1:8000/admin/chat?q=Hello"
```
In terminal, curl cannot auto escape special characters, so you can use browser to test. Just copy the URL to your browser, replace "Hello" with your words.

### Local Development
1. Clone the repository:
```bash
git clone https://github.com/crestalnetwork/intentkit.git
cd intentkit
```

2. Set up your environment:
Python 3.10-3.12 are supported versions, and it's recommended to use 3.12.
If you haven't installed `poetry`, please install it first.
We recommend manually creating a venv; otherwise, the venv created automatically by Poetry may not meet your needs.
```bash
python3.12 -m venv .venv
source .venv/bin/activate
poetry install --with dev
```

3. Configure your environment:
```bash
cp example.env .env
# Edit .env with your configuration
```

4. Run the application:
```bash
# Run the API server in development mode
uvicorn app.api:app --reload

# Run the autonomous agent scheduler
python -m app.autonomous
```

"Create Agent" and "Try it out" refer to the Docker section.

## The Model
For now, we only support any model from OpenAI and DeepSeek.  
We will support more models in the future.

## Integrations

### Twitter
[Twitter Integration](docs/twitter.md)

### Coinbase
[Coinbase Integration](docs/skills/cdp.md)

## Configuration

The application can be configured using environment variables or AWS Secrets Manager. Key configuration options:

- `ENV`: Environment (local or others)
- `DB_*`: PostgreSQL Database configuration (Required)
- `OPENAI_API_KEY`: OpenAI API key for agent interactions (Required)
- `CDP_*`: Coinbase Developer Platform configuration (Optional)

See `example.env` for all available options.

## Project Structure

- `abstracts/`: Abstract classes and interfaces
- `app/`: Core application code
  - `core/`: Core modules
  - `services/`: Services
  - `entrypoints/`: Entrypoints means the way to interact with the agent
  - `admin/`: Admin logic
  - `config/`: Configurations
  - `api.py`: REST API server
  - `autonomous.py`: Autonomous agent scheduler
  - `twitter.py`: Twitter listener
  - `telegram.py`: Telegram listener
- `models/`: Database models
- `skills/`: Skill implementations
- `skill_sets/`: Predefined skill set collections
- `plugins/`: Reserved for Plugin implementations
- `utils/`: Utility functions

## Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) before submitting a pull request.

### Contribute Skills

# How to Contribute

We welcome contributions to the IntentKit project!
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# The start command handler
def start(update: Update, context: CallbackContext) -> None:
    # Sending a friendly greeting message
    update.message.reply_text("Hello! 😊 I'm happy you're here. How can I help you today? 🌟")
    
    # Asking the first question or starting the conversation
    update.message.reply_text("What would you like to know or do? Feel free to ask me anything!")

# Function to set up the bot
def main():
    # Replace 'YOUR_TOKEN' with your actual bot token
    updater = Updater("YOUR_TOKEN")
    
    # Adding the start command handler
    updater.dispatcher.add_handler(CommandHandler("start", start))
    
    # Start the bot
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
ository.

## Code Style
Follow the existing code style and structure of the project. Ensure that your code is clean and well-commented.
ء
See the [Skill Development Guide](docs/contributing/skills.md) for more information.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
git commit -m "Update README with friendly greeting messages"

git push origin main



