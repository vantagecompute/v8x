---
title: Troubleshooting
description: Common issues and solutions for v8x
---

Quick answers for frequent issues.

## v8x Authentication Fails

```bash
v8x login  # complete device flow in browser
```

If the terminal shows a "loop": verify network access to OIDC URL and that system clock skew < 60s.

## Expired Token

```bash
v8x whoami  # triggers refresh if possible
v8x login   # re-authenticate if still failing
```

## Profile Not Found

```bash
v8x profile list
v8x profile create dev --activate
```

## JSON Output / Parsing Errors

Ensure you used `--json` before piping to `jq`:

```bash
v8x cluster list --json | jq '.clusters | length'
```

## Network / API Errors

- Add `-v` for debug logs
- Confirm configured endpoints

## Token Cache Corruption

Remove token file (path may differ by install) then re-login:

```bash
rm ~/.config/v8x/tokens/<profile>.json 2>/dev/null || true
v8x login
```

## Rate Limits / Throttling

Retry after brief backoff; excessive rapid polling may be limited.

## Still Stuck?

Open an issue including: command run, abbreviated error, Python version, profile name (not tokens).
