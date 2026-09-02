# EasyCode Published Skills

This repository is the source backup for the skills currently published in the EasyCode Marketplace.

It intentionally contains only the 19 skills that are currently externally available from the production marketplace. Personal, experimental, unpublished, and locally maintained skills are not included.

## Layout

Each skill is stored as source under `skills/<skill-name>/` and has a root `SKILL.md` file. Its committed `marketplace.json` preserves versioned Marketplace metadata: active state, usage example, icon, detail previews, preview thumbnails, example output files, and stable object-storage keys. Runtime caches and package-manager dependencies are excluded so that the repository remains reviewable and is suitable for source control.

## Publishing scope

This repository is a source snapshot and does not itself change Marketplace visibility. Publishing or updating object storage is handled by the Marketplace release workflow.
