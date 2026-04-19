# Release v0.17.58

## Improvements

- Improved reliability for agents with large skill catalogs. Built-in capabilities — current time, long-term memory, posts, activities, and sub-agent calls — now remain available even when the automatic tool-selection layer narrows the active tool set. Previously these core tools could be filtered out, causing agents to repeatedly attempt the same failed call without recovering.
- Raised the threshold at which the automatic tool-selection layer activates and refined the counting logic so built-in provider tools no longer push borderline agents into the selection path prematurely.

**Full Changelog**: https://github.com/crestalnetwork/intentkit/compare/v0.17.57...v0.17.58
