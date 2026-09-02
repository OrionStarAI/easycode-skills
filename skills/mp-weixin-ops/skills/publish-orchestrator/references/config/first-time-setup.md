---
name: first-time-setup
description: First-time setup flow for publish-orchestrator preferences
---

# First-Time Setup

## Overview

When no EXTEND.md is found, guide user through preference setup.

**BLOCKING OPERATION**: This setup MUST complete before ANY other workflow steps. Do NOT:
- Ask about content or files to publish
- Ask about themes or publishing methods
- Proceed to content conversion or publishing

ONLY ask the questions in this setup flow, save EXTEND.md, then continue.

## Setup Flow

```
No EXTEND.md found
        |
        v
+-----------------------+
| Step 0: IP Whitelist  |
| (check API readiness) |
+-----------------------+
        |
        v
+---------------------+
| AskUserQuestion     |
| (all questions)     |
+---------------------+
        |
        v
+---------------------+
| Create EXTEND.md    |
+---------------------+
        |
        v
    Continue to Step 1
```

## Step 0: IP Whitelist Check

Before proceeding with preferences, verify that the server IP is in the WeChat IP whitelist. This is required for the API to work.

### Check Flow

1. Get current public IP:
```bash
curl -s ifconfig.me
```

2. Ask user: "Is this IP already in your WeChat IP whitelist?"
   - If YES → continue to preferences
   - If NO → guide user through adding it (see below)

### How to Add IP Whitelist

Guide the user step by step:

1. Log in to WeChat Official Account backend: https://mp.weixin.qq.com
2. Go to 「设置与开发」→「基本配置」
3. Find「开发者ID(AppID)」section, locate「IP白名单」
4. Click「修改」
5. Add the server IP (from `curl ifconfig.me`)
6. Save

> **Note:** Without IP whitelist, API calls will fail with error `40164: invalid ip xxx, not in whitelist`.

## Questions

**Language**: Use user's input language or saved language preference.

Use AskUserQuestion with ALL questions in ONE call:

### Question 1: Default Theme

```yaml
header: "Theme"
question: "Default theme for article conversion?"
options:
  - label: "default (Recommended)"
    description: "Classic layout - centered title with border, white-on-color H2"
  - label: "grace (DO NOT USE - layout issues)"
    description: "⚠️ Has serious layout issues, use default instead"
  - label: "simple"
    description: "Minimal modern - asymmetric rounded corners, clean whitespace"
```

### Question 2: Default Publishing Method

```yaml
header: "Method"
question: "Default publishing method?"
options:
  - label: "api (Recommended)"
    description: "Fast, requires API credentials (AppID + AppSecret)"
  - label: "browser"
    description: "Slow, requires Chrome and login session"
```

### Question 3: Default Author

```yaml
header: "Author"
question: "Default author name for articles?"
options:
  - label: "No default"
    description: "Leave empty, specify per article"
```

Note: User will likely choose "Other" to type their author name.

### Question 4: Open Comments

```yaml
header: "Comments"
question: "Enable comments on articles by default?"
options:
  - label: "Yes (Recommended)"
    description: "Allow readers to comment on articles"
  - label: "No"
    description: "Disable comments by default"
```

### Question 5: Fans-Only Comments

```yaml
header: "Fans only"
question: "Restrict comments to followers only?"
options:
  - label: "No (Recommended)"
    description: "All readers can comment"
  - label: "Yes"
    description: "Only followers can comment"
```

### Question 6: Save Location

```yaml
header: "Save"
question: "Where to save preferences?"
options:
  - label: "Project (Recommended)"
    description: ".secrets/ (this project only)"
  - label: "User"
    description: "~/.config/publish-orchestrator/ (all projects)"
```

## Save Locations

| Choice | Path | Scope |
|--------|------|-------|
| Project | `config/config.json` | Current project |
| User | `~/.config/publish-orchestrator/config.json` | All projects |

## After Setup

1. Create directory if needed
2. Write EXTEND.md
3. Confirm: "Preferences saved to [path]"
4. Continue to Step 0 (load the saved preferences)

## EXTEND.md Template

```md
default_theme: [default/simple]
default_publish_method: [api/browser]
default_author: [author name or empty]
need_open_comment: [1/0]
only_fans_can_comment: [1/0]
chrome_profile_path:
```

## Modifying Preferences Later

Users can edit EXTEND.md directly or delete it to trigger setup again.
