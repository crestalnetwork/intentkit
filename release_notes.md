# Release v2.39.0

## Model Updates

- **GLM 5.3 Flash** — Z.ai's new flash model replaces GLM 4.7 Flash. It is a major step up: a 1M-token context window (5x larger), it can now read images and video, and it reasons on every request. It launches at half price, so it currently costs only slightly more than the model it replaces. Agents on GLM 4.7 Flash move over automatically.
- **Qwen3.8 Flash** — Alibaba's newest flash model replaces Qwen3.7 Flash, with better quality across the board and double the maximum output length. Agents on the previous version move over automatically.
- **Ox Alpha has been retired.** The free preview period for this anonymous stealth model has ended and its provider has withdrawn it. By all the evidence it was GLM 5.3 Flash in disguise, so the same model remains available above under its real name. The few agents created with Ox Alpha as their model during the one-week trial need to be pointed at another model; new agents default to Gemini 3.7 Flash again.

## Improvements

- Strengthened the safeguards on the model catalog so that models routed through OpenRouter are always served by their vetted upstream provider.
