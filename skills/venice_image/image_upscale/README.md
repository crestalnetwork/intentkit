# image_upscale

**Image Upscale** is a sub-tool of the Venice Image suite. It uses Venice AI’s powerful super-resolution models to increase the size and clarity of images by 2x or 4x, making low-resolution images suitable for HD displays, print, or content enhancement. This is not just simple pixel stretching—it uses AI to intelligently recreate additional detail, texture, and smoothness.

---

## What does it do?

Given any publicly accessible image URL, the tool fetches the image, applies deep-learning upscaling (super-resolution), and returns a new image URL to the upscaled output. Users can choose between 2x or 4x upscaling depending on needs, and can optionally control how much "realism"/texture is preserved from the original.

Key benefits:
- Consistent color, sharpness, and clarity at higher resolutions
- AI removes pixelation and can reduce compression artifacts
- Optional "replication" factor lets you tune how much of the original’s noise/detail is restored

---

## Input

| Field        | Type             | Description                                                                                          | Required | Default |
|--------------|------------------|------------------------------------------------------------------------------------------------------|----------|---------|
| image_url    | HttpUrl          | Public URL to the image you want to upscale.                                                         | Yes      |         |
| scale        | Literal[2, 4]    | The scaling factor (2 for 2x, 4 for 4x enlargement).                                                 | Yes      | 2       |
| replication  | float (0.1–1.0)  | How much to preserve edges, texture, and noise from original (higher = more detail, less smoothing). | No       | 0.35    |

Example:
```json
{
  "image_url": "https://example.com/photo.jpg",
  "scale": 4,
  "replication": 0.5
}
```

---

## Output

On success, returns a result dictionary containing at least:
- `success`: true
- `result`: URL for the upscaled image (typically hosted on S3 or compatible object storage)
- Additional metadata as needed

Example:
```json
{
  "success": true,
  "result": "https://s3.storage.example/venice_image/image_upscale/1a2b3c....png"
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

- **Photo Restoration** – Upscale old, small web images for print or display
- **Content Creation** – Create HD assets from AI-generated or web-ripped images
- **Design/Prototyping** – Improve source assets for posters, presentations, or large canvas
- **Archival** – Enhance legacy digital art or research scans

---

## Advanced Notes

- Works for all common raster formats (JPG, PNG, WEBP). Unsupported types are auto-converted to PNG.
- "Replication" factor explanation:
  - **Low values (e.g., 0.1–0.25):** smoother, less noise, more “plastic” look (good for AI/clean results)
  - **High values (e.g., 0.7–1.0):** preserves original photo noise/texture, less smoothing (good for art/photo upscaling)
- Original aspect ratio is always preserved.

---

## Limitations

- Does not add content—only increases fidelity of existing features.
- Output detail is limited by source image quality and AI model limits.
- NSFW images will be blurred if safe mode is enabled.

---

## Example Usage (Pseudo-code)

```python
result = await agent.send_tool(
    "image_upscale",
    {
        "image_url": "https://somehost.com/image.png",
        "scale": 2,
        "replication": 0.4
    }
)
upscaled_url = result["result"]
```

---

## Compliance & Attribution

- You must have rights to use the supplied image.
- Follows [Venice AI terms of service](https://venice.ai/).

---