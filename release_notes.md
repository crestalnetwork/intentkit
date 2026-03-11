## New Features

- **Copy as Markdown**: Post pages now include a "Copy as Markdown" button next to the title, allowing users to copy the full post content (with title) as raw Markdown.
- **Post Card in Chat**: When an agent creates a post, a clickable card is automatically sent to the user in the chat, linking directly to the post. The AI no longer needs to separately summarize or display the post.
- **`APP_BASE_URL` Config**: Added a new `APP_BASE_URL` configuration option for the frontend base URL, used for generating post links.

## Improvements

- Card links in chat now open in the current window when linking to the same site, and in a new tab for external links.
- Fixed `/post/:id` route returning 404 for dynamic post IDs.
- Cleaned up unused prompt code.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.11.24...v0.11.25
