---
title: Notebooks
description: Notebook workflow status in v8x
---

## Notebook Commands

The current `v8x` CLI does not expose a top-level `notebook` command. Older examples that used `vantage notebook ...` are no longer valid for this CLI.

Use the Vantage web interface for notebook server lifecycle operations, or use the current CLI primitives around clusters, storage, and jobs:

```bash
# Find the target cluster
v8x cluster list

# Create or list storage that a notebook workload can mount
v8x storage create notebook-home <cluster-name> --namespace <namespace> --size 100Gi
v8x storage list <cluster-name> --namespace <namespace>

# Track batch jobs associated with notebook-adjacent workflows
v8x job submission list
v8x job submission get <submission-id>
```

If notebook-specific commands are reintroduced, this page should be updated from the live `v8x --help` output.