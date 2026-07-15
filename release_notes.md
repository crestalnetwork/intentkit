# Release v2.25.0

## New Features

- **Reasoning effort per agent**: agents can now set how much thinking their model does before answering — from none up to max — right next to the model choice. Leave it unset to use the model's recommended default. The setting automatically adapts to each model's real capabilities: models that can't turn thinking off run at their lightest level, and models with a simple on/off switch map your choice sensibly. The team lead can also configure this when creating or updating agents.

## Improvements

- **Model lineup cleanup**: retired the MiniMax M2 Her and Grok 4.20 models. Agents still using them switch automatically to MiniMax M3 and Grok 4.5 (Grok 4.5 is the newer model despite the smaller version number).
- Fixed an issue where MiniMax M3 connected directly was not using its thinking mode.
