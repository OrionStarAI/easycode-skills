# EasyCode Published Skills

This repository is the source backup for the skills currently published in the EasyCode Marketplace.

It intentionally contains only the 19 skills that are currently externally available from the production marketplace. Personal, experimental, unpublished, and locally maintained skills are not included.

## Layout

Each skill is stored as source under `skills/<skill-name>/` and has a root `SKILL.md` file. Its committed `marketplace.json` preserves versioned Marketplace metadata: active state, usage example, icon, detail previews, preview thumbnails, example output files, and stable object-storage keys. Runtime caches and package-manager dependencies are excluded so that the repository remains reviewable and is suitable for source control.

## Publishing scope

This repository is a source snapshot and does not itself change Marketplace visibility. Publishing or updating object storage is handled by the Marketplace release workflow.

## Automation and review gates

Upstream-backed skills declare a fixed GitHub repository, source path, and reviewed commit in their `SKILL.md` frontmatter. The **Sync upstream skills** workflow checks those sources daily at 02:00 UTC (and can be started manually), then opens a review PR when an upstream changes. It performs a three-way merge and leaves conflicts for a maintainer; it never writes directly to EasyCode or object storage.

Every pull request and push to `main` runs **Skill Gate**. The gate parses YAML frontmatter with a real YAML parser, validates `marketplace.json` and committed media, rejects unsafe paths and merge markers, and scans for common credentials and private keys. It includes a regression test for the unquoted-colon description error that previously made the Remotion skill disappear from the client.

See [docs/skill-sync.md](docs/skill-sync.md) for metadata, conflict handling, and the release hand-off. After a reviewed merge, the existing OpenC3 `release-online-*` tag flow remains the step that publishes the Marketplace package and synchronizes object storage.
