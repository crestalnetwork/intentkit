# Venice Image Skill Suite

Venice Image is a comprehensive skill suite for intelligent agents, enabling state-of-the-art AI image generation, enhancement, upscaling, and vision analysis using the [Venice AI API](https://venice.ai/). This suite offers a modular interface: each sub-tool covers a focused aspect of visual intelligence, while sharing unified configuration and error handling.

---

## Features

### 1. **Image Generation**
Prompt-based creation of new artworks or photorealistic images, with support for multiple leading AI models, extensive style presets, and negative prompting. Models include:
- **Fluently XL** (realism, professional art)
- **Flux Dev** (innovative research, art workflows)
- **Lustify SDXL** (photorealistic, NSFW/SFW)
- **Pony Realism** (anime/character detail, Danbooru tags)
- **Venice SD35 / Stable Diffusion 3.5** (Stability AI, creative design)

### 2. **Image Enhancement**
Stylize or refine *existing* images without changing their resolution—ideal for artistic edits, restoration, or visual polishing.

### 3. **Image Upscaling**
Increase resolution by 2x or 4x while preserving essential details (with optional noise/replication settings). Great for preparing web images for print or HD use.

### 4. **Image Vision**
Obtain highly detailed, context-rich textual descriptions of images—useful for content understanding, accessibility, indexing, or cognitive agents.

---

## How It Works

- Tools call the Venice API via secure network requests, automatically handling authentication, rate limiting, and error management.
- Any generated or processed images are transparently stored in an object store (S3 or compatible), with returned URLs ready for user consumption.
- Unified logging and troubleshooting: every tool shares a robust diagnostic backbone for consistent developer experience.

---

## Setup and Configuration

All skills require a **Venice API key** for operation.

### Required Configuration
- `enabled` *(bool)*: Enable or disable the overall skill suite.
- `api_key` *(string, sensitive)*: Your [Venice AI API key](https://venice.ai/).
- `states`: Enable/disable and set visibility for each sub-tool (public/private/disabled).

### Advanced Options
- `safe_mode` *(bool, default: true)*: If true, blurs images classified as adult/NSFW.
- `hide_watermark` *(bool, default: true)*: Request images without a Venice watermark (subject to Venice policy).
- `embed_exif_metadata` *(bool, default: false)*: Whether to embed prompt/config info in EXIF metadata.
- `negative_prompt` *(string)*: Default negative prompt, e.g. `(worst quality: 1.4), bad quality, nsfw`.
- `rate_limit_number` / `rate_limit_minutes`: (optional) Set a max request rate per agent.

For per-tool configuration, refer to the `states` section in [schema.json](schema.json):
- Each tool (e.g. `image_generation_flux_dev`, `image_enhance`, etc.) can be set to `"public"` (all users), `"private"` (agent owner only), or `"disabled"` (hidden).

#### Example (YAML/JSON-like)
```json
{
  "enabled": true,
  "api_key": "<YOUR_VENICE_API_KEY>",
  "safe_mode": true,
  "states": {
    "image_vision": "public",
    "image_enhance": "private",
    "image_upscale": "disabled",
    "image_generation_flux_dev": "public"
  }
}
```

---

## Usage Patterns

Each sub-tool has its own standardized input:
- URL-based tools (`image_enhance`, `image_upscale`, `image_vision`) require a web-accessible image URL.
- Generation tools require a *prompt* and offer flexible parameters (size, style, negative prompt, etc).

Errors and troubleshooting info are always returned in a structured dictionary, with clear separation of success and error fields.

---

## Output and Storage

- All generated/processed images are written to S3-compatible storage using a SHA256-based unique key.
- Returned URLs are agent-accessible and stable.
- For Vision and non-binary results, the output is returned inline as a dictionary.

---

## Security, License & Compliance

- Your Venice API key is required and kept confidential per config practices.
- Generated images and tool usage are subject to [Venice AI Terms of Service](https://venice.ai/) and the terms of the respective models (e.g. Stability AI, Black Forest Labs).
- Agents should implement their own access and moderation layers; Safe Mode and watermarking are best-effort.

---

## Included Sub-Tools

_(For detailed docs, see the respective sub-tool README entries.)_

- image_generation_fluently_xl
- image_generation_flux_dev
- image_generation_flux_dev_uncensored
- image_generation_lustify_sdxl
- image_generation_pony_realism
- image_generation_venice_sd35
- image_generation_stable_diffusion_3_5
- image_enhance
- image_upscale
- image_vision

---

## Contributing & Support

For issues, bugfixes, or requests, please open a GitHub issue or contact the maintainers. This suite is regularly updated as Venice AI evolves.

---
