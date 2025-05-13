# Agent Management

## Use Shell Scripts

We have provided some [helper shells](../scripts/) for your convenience.

When you use these scripts, make sure you have started the [api server in localhost](../DEVELOPMENT.md).

For example, we want to create an agent, id is `example`, first cd into the directory:

```bash
cd scripts
```

**Create Agent:**
```bash
sh create.sh example
```

Now you have a blank agent, let's add features to it.

**Export Agent:**
```bash
sh export.sh example
```

Edit the agent config file: `example.yaml`. Then import it.

**Import Agent:**
```bash
sh import.sh example
```

**Test Your Agent:**

You can test your agent using API calls or the IntentKit Sandbox UI. The UI provides a visual chat interface for interacting with your agents. See the [IntentKit Sandbox UI repository](https://github.com/bluntbrain/intentkit-sandbox-ui) for setup and usage.

## Advanced Agent API

You can visit the [API Docs](http://localhost:8000/redoc#tag/Agent) to learn more.

## The Prompt
In agent config, there are 5 fields about prompt, they are `purpose`, `personality`, `principles`, `prompt`, `prompt_append`.  
IntentKit will compose `purpose`, `personality`, `principles`, `prompt` to `system_prompt`.

### LLM Interaction
The models cannot remember anything, so every time we interact with it, we have to provide all the 
background information and interaction context (that is, additional knowledge and memory).  
What we send to the large model looks something like this:
- System: `system_prompt`
- User: conversation history
- Assistant: conversation history
- ...
- User: conversation history
- Assistant: conversation history
- User: currently being said 
- System: `prompt_append` (Optional)

The content of the system role is to inform the AI that it is being addressed by an administrator, 
so it should not treat you like an user. However, your permissions are not necessarily always higher 
than those of regular users; you simply have the advantage of being the first to set various rules 
for the AI to follow according to your logic.  
For example, you can tell it that the system role has the highest authority, and if the user role 
requests an action that violates the rules set by the system role, you should deny it.

### Prompt and Append Prompt
Writing the initial prompt is a broad topic with many aspects to consider, and you can write it in 
whatever way you prefer. Here, I will only address the prompt_append.  
We've found that if you emphasize the most important rules again at the end, it significantly increases 
the likelihood of the AI following your rules. You can declare or repeat your core rules in this section.  
One last tip: the AI will perceive this information as having been inserted just before it responds to the user, 
so avoid saying anything like "later" in this instruction, as that "later" will never happen for the AI.
