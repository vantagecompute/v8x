---
title: Private Vantage Installation
description: Configure the v8x to work with 3rd Party/Partner Vantage Installations
---

## 1. Connect to a private Vantage deployment

Install and verify the CLI first with the [Installation Guide](./installation).

The `v8x` comes preconfigured to work with [https://vantagecompute.ai](https://vantagecompute.ai) by default.

If you are connecting to a privately hosted Vantage instance you will need to set up your profile accordingly.

Create and activate a profile:

```bash
v8x profile create vantage-example-com \
  --vantage-url https://app.example.vantagecompute.ai

v8x profile use vantage-example-com
```

The profile's only deployment-specific argument is `--vantage-url`. The CLI derives the related API and authentication endpoints from that Vantage URL.

## 2. Inspect Identity

```bash
v8x whoami
```

```bash
v8x whoami --json | jq '{email: .identity.email, profile: .profile}'
```

---
See also: [Commands](./commands) | [Troubleshooting](./troubleshooting)
