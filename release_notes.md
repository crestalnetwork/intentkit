# Release v2.27.1

## Improvements

- Smarter image storage: when an agent tries to persist an image that is already hosted on our CDN (for example, one it just generated), the existing link is now returned directly instead of downloading and uploading a duplicate copy. This eliminates wasted transfers and duplicate files in storage.
