# Venice Image Tool Suite

Venice Image is a comprehensive tool suite for intelligent agents, enabling state-of-the-art AI image generation, enhancement, upscaling, and vision analysis using the [Venice AI API](https://venice.ai/). This suite offers a modular interface: each sub-tool covers a focused aspect of visual intelligence, while sharing unified configuration and error handling.

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

All tools require a **Venice API key**, configured at the system level
(`VENICE_API_KEY`). Enable individual tools by adding their names to the
agent's `tools` list, e.g.:

```yaml
tools:
  - venice_image_vision
  - venice_image_enhance
  - venice_image_generation_flux_dev
```

Generation behaviour (safe mode, watermark, negative prompt, ...) is set
per call through each tool's arguments.

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
