# Release v2.23.0

## Improvements

- **Models now run on provider-recommended settings**: manual tuning knobs (temperature and repetition penalties) are retired across agents and templates. Current-generation models are optimized for their providers' defaults — several reject or silently ignore manual values — so every model now runs the way its maker intended, with no configuration needed.
- **Smarter reasoning control for DeepSeek**: DeepSeek models now switch thinking mode on or off exactly as configured, so the fast variant responds quicker and no longer spends hidden reasoning effort.
- Fixed an invalid reasoning setting on the GPT-5.6 Luna model.
