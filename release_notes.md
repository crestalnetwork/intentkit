# Release v2.33.0

## Security

- **Closed a server-side request forgery hole reported privately by an outside security researcher.** The website scraping tools fetched any address an agent conversation named, without checking where it pointed. That let the platform be steered at its own internal network or at a cloud provider's metadata service, and because the scraper indexes what it retrieves, the response could then be read back out of the agent's knowledge base.

- **Every tool that fetches an address is now protected by one shared check, not several.** The platform previously carried three separate versions of this protection, each covering slightly different ground, and several fetching paths had none at all. All of them now share a single check that classifies the destination before the request, again after the address is resolved, and once more for every hop when a site forwards the request elsewhere. Anything aimed at an internal, reserved, or metadata address is refused before a connection is opened.

- **The shared check also covers routes the previous versions missed**, including addresses that resolve to an internal destination only at request time, IPv6 wrappers around internal addresses, and the metadata endpoints of additional cloud providers. Fetching tools that had no protection at all — image editing and upscaling, image inputs to the image generators, paid HTTP requests, link previews, and stored-image downloads — are now covered on the same terms.

## Improvements

- Web page reading is cheaper and more reliable: plain-text and data endpoints are fetched directly instead of going through the browser-rendering service, rendering calls are paced to stay inside the service's rate limit, and rate-limit responses are retried automatically.
- Publishing a post no longer fails when extra or blank tags are supplied; the extras are dropped instead of wasting the agent's turn.
- Internal helper tasks such as page cleanup, memory merging, and search result formatting no longer spend reasoning effort on mechanical work, cutting a substantial amount of weekly token usage with no change in output quality.
