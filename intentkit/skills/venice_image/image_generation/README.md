# Venice Image Generation Tools

Venice Image Generation provides flexible, prompt-based image creation using multiple state-of-the-art AI models via the Venice AI API. These tools support a broad spectrum of styles, subject matter, and output formats, making it ideal for artists, designers, marketers, research, and personal creativity.

---

## Overview

- **Purpose:** Synthesize original images from natural-language prompts.
- **Supported Models:** Choose from several world-class models, each suited for different tasks:
    - **Fluently XL:** Professional realism, lighting, artistic work.
    - **Flux Dev:** Artistic research, innovative and creative workflows.
    - **Flux Dev Uncensored:** For unrestricted, uncensored generation (including NSFW).
    - **Lustify SDXL:** Photorealistic, NSFW/SFW versatility.
    - **Pony Realism:** High-detail anime/character design (great with Danbooru tags).
    - **Venice SD35/Stable Diffusion 3.5:** Artistic, illustrative, or design content, powered by Stability AI.
- **Unified Interface:** Each model is its own sub-tool, but all support the same core set of options.

---

## Input Parameters

| Field            | Type                            | Description                                                                                            | Required | Default        |
|------------------|---------------------------------|--------------------------------------------------------------------------------------------------------|----------|---------------|
| prompt           | string                          | Main description of the image to generate. Use detailed, specific language for best results.           | Yes      |               |
| model_id         | string (see below)              | AI model to use. Each sub-tool sets its own model_id internally.                                       | N/A      | (hardcoded)    |
| width            | int (max 2048)                  | Output image width (pixels). Must be multiple of 8 or 16 depending on model.                           | No       | 1024          |
| height           | int (max 2048)                  | Output image height (pixels).                                                                          | No       | 1024          |
| format           | "png" \| "jpeg" \| "webp"       | Output image format.                                                                                   | No       | png           |
| style_preset     | string (enumerated)             | Optional visual preset (e.g., "Photographic", "Anime", "Abstract", etc.). See full list below.         | No       | Photographic   |
| negative_prompt  | string                          | Exclude these elements or concepts from the image (e.g. “nsfw, low quality”).                          | No       | suite default  |
| seed             | int                             | Control randomness. Reuse a value for repeatability.                                                   | No       | random         |
| cfg_scale        | float (e.g. 1–20)               | Prompt fidelity – higher = closer adherence to prompt, lower = more variety.                           | No       | 7.5           |
| return_binary    | bool                            | Always `False`. Output is a hosted URL, not inline binary.                                             | N/A      | False         |
| safe_mode        | bool                            | If enabled, applies content filtering / blurring for NSFW.                                             | Inherited | true         |
| embed_exif_metadata | bool                         | If enabled, embeds prompt info in output EXIF metadata.                                                | Inherited | false         |
| hide_watermark   | bool                            | Hide the Venice watermark, where possible.                                                            | Inherited | true           |

#### Example Prompt:
> "In the style of a Renaissance oil painting, a fierce orange tabby cat with a crown, surrounded by lush velvet drapery and golden sunlight."

#### Style Presets
An extensive list is included, for example:
- "Photographic"
- "Anime"
- "Cinematic"
- "Digital Art"
- "Abstract"
- "Cubist"
- ...and over 30 more. See documentation or schema for the full list.

#### Example Input:
```json
{
  "prompt": "A highly detailed portrait of a robot playing chess, cinematic lighting, photoreal 4k",
  "width": 1536,
  "height": 1024,
  "format": "jpeg",
  "style_preset": "Cinematic",
  "cfg_scale": 10,
  "negative_prompt": "text, watermark, blurry",
  "seed": 424242
}
```

---

## Output

The tool returns a dict that includes:

- `success`: true/false
- `image_url`: The URL to the generated image (stored in S3 or similar object storage)
- Additional metadata (generation params, seed, etc.)

Example:
```json
{
  "success": true,
  "image_url": "https://s3.my-storage.net/venice_image/fluently-xl/abc123f....png",
  "seed": 424242,
  "generation_time_s": 22.4
}
```

On error:
```json
{
  "success": false,
  "error": "API returned error: prompt too long",
  "result": null
}
```

---

## Advanced Capabilities

- **Inpainting**: Modify regions of an existing image with precise mask and text controls (see schema for input structure).
- **EXIF Embedding**: If enabled, the tool can embed the prompt/config info in the output file’s EXIF metadata.

---

## Use Cases

- **Art & Design:** Instantly create drafts, mood boards, or finished art for any assignment
- **Marketing/Content:** Rapid visual ideation for blog posts, social media, ads, covers, etc.
- **Ideation/Research:** Visualize concepts, inventions, or speculative scenarios quickly
- **Education:** Generate visual teaching content on demand
- **Character/Concept Design:** Leverage anime/artistic models for avatars, OC creation, comics

---

## Limitations

- Results are only as good as your prompt and model choice.
- NSFW filtering varies by model; check the tool’s description and enable `safe_mode` for safety.
- Some style/subject combinations may not be supported by a given model.
- Stable Diffusion/Flux Dev variants may have license restrictions—review Venice API and model TOS.

---

## Example Usage (Pseudo-code)

```python
result = await agent.send_tool(
    "image_generation_fluently_xl",
    {
        "prompt": "A futuristic cityscape at sunset, neon lights, flying cars, cinematic",
        "style_preset": "Cinematic",
        "width": 1280,
        "height": 704
    }
)
url = result["image_url"]
```

---

## Compliance & Attribution

You must respect [Venice AI terms of service](https://venice.ai/) and the terms and licenses of the selected model.

---
