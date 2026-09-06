---
name: remotion-docs
description: Search Remotion documentation
version: 4.0.521
---

This skill teaches you how to discover and read current Remotion documentation.
If this is not relevant, load [Remotion Best Practices](../SKILL.md) instead.

## Discovering the docs

Use the official Remotion documentation site's search, or a web search restricted
to `site:remotion.dev/docs <your query>`, to find relevant documentation pages.
Do not use embedded third-party search credentials or ask a user to provide one
for ordinary documentation lookup.

## Fetching a page as Markdown

Append `.md` to any Remotion docs URL to retrieve its Markdown source (saves tokens):

```
https://www.remotion.dev/docs/use-video-config.md
https://www.remotion.dev/docs/sequence.md
https://www.remotion.dev/docs/lambda/rendermediaonlambda.md
```

## Workflow

1. Search the official docs for the concept or API you need.
2. Pick the most relevant URL or URLs from the results.
3. Fetch each URL with the `.md` suffix.
4. Implement using the current documentation rather than memorized API knowledge.
