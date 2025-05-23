# image_enhance

**Image Enhance** enables you to improve, stylize, or refine an existing image using the Venice AI enhancer. Unlike upscaling, this tool keeps the original image size but substantially upgrades its visual quality, style, or texture—ideal for creative, restoration, or polishing use-cases.

---

## What does it do?

- Accepts a publicly accessible image URL.
- Uses a provided prompt to guide the desired enhancement—e.g., style, artistic direction, or quality upgrades (such as “gold accents”, “vivid color”, “oil painting”, or “gentle watercolor”).
- Supports adjustment of the intensity of enhancement and how much original detail is preserved (creativity & replication).
- Returns a new image (matching original dimensions) with enhanced appearance and style.

Typical uses:
- Sharpen and clarify blurry images.
- Instantly “re-theme” a photo or artwork (color, material, style transfer).
- Polish images for social, ecommerce, professional, or creative projects.

---

## Input Parameters

| Field             | Type          | Description                                                                                                      | Required | Default |
|-------------------|---------------|------------------------------------------------------------------------------------------------------------------|----------|---------|
| image_url         | str (HttpUrl) | Publicly accessible URL of the image to enhance                                                                  | Yes      |         |
| enhancePrompt     | str           | **Describes the desired enhancement, style, or theme.** Concise, descriptive terms work best.                    | Yes      |         |
| replication       | float         | How much of the original image structure, lines, and noise are retained (0.1–1.0).                               | No       | 0.35    |
| enhanceCreativity | float         | How far the AI can diverge from the original (0 = subtle, 1 = max stylization/new image).                        | No       | 0.5     |

**Prompt Examples (for `enhancePrompt`):**
- `"marble, gold veins, high contrast"`
- `"vaporwave color palette, cyberpunk lighting"`
- `"oil painting, impasto brushwork"`
- `"smooth skin, brighten shadows, cinematic look"`

Example input:
```json
{
  "image_url": "https://img.site/old-photo.png",
  "enhancePrompt": "soft watercolor, pastel tones, gentle light",
  "replication": 0.25,
  "enhanceCreativity": 0.7
}
```

---

## Output

On success, returns:
```json
{
  "success": true,
  "result": "https://s3.storage.example/venice_image/image_enhance/ab12cd...png"
}
```

On error:
```json
{
  "success": false,
  "error": "Failed to fetch or validate image from URL: ...",
  "result": null
}
```

---

## Typical Use Cases

- **Commerce/Product Images**: Instantly polish web photos for catalogs or listings.
- **Restoration**: Revive faded or dated artwork/photos for social, framing, or print.
- **Style Transfer**: Make a photo look like “stained glass”, “anime cel”, or “movie still”.
- **Social & Art Creation**: Quickly freshen up images for sharing with a unique twist.

---

## Advanced Notes

- **Replication**:  
  - Lower (`~0.1`): AI smooths out noise/details, crisper/cleaner look.
  - Higher (`~0.9`): Retain original grit, preserve realistic features, more subtle change.
- **EnhanceCreativity**:  
  - Lower (`0.0`): Only very minor tweaks.
  - Higher (`1.0`): Might look like a fully new artwork in the target style.
- **Image must be accessible and in a supported format**; conversion to PNG is automatic if needed.
- **Original resolution is kept**; for larger output, use `image_upscale` after enhancement.

---

## Limitations

- Does not increase resolution—use in conjunction with upscaling for large deliverables.
- Not a restoration-of-lost-content tool: Real degradation or loss isn’t recoverable, though apparent fidelity can be improved.
- The style quality depends on the provided enhancement prompt and the source image clarity.

---

## Example Usage (Python-esque pseudocode)

```python
result = await agent.send_tool(
    "image_enhance",
    {
        "image_url": "https://cdn.site/photo.jpg",
        "enhancePrompt": "marble, gold details, glowing edges",
        "enhanceCreativity": 0.9
    }
)
enhanced_url = result["result"]
```

---

## Attribution & Compliance

Use of this tool is subject to [Venice AI terms of service](https://venice.ai/) and applicable copyright law for input images.

---