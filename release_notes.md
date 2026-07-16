# Release v2.26.3

## Improvements

- Fixed GPT image generation when running through OpenRouter: requests now go to the correct image endpoint, so `image_gpt` and `image_gpt_mini` work again without a native OpenAI key.
- Publishing posts is more forgiving: an overlong URL slug no longer fails the whole request — it is now shortened automatically at a word boundary.
