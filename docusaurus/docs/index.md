---
title: "v8x - The Vantage Compute CLI"
description: "Authenticate, manage profiles, register cloud accounts, create clusters, and deploy local Vantage applications"
slug: /
---

## The unified command-line interface for Vantage Compute

`v8x` is the command-line interface for authenticating with Vantage Compute, managing profiles, registering cloud accounts, creating clusters, and launching supported deployment applications.

### Quick Start

Install from PyPI with `uv`:

```bash
uv tool install v8x
v8x --help
```

Or run from source:

```bash
git clone https://github.com/vantagecompute/v8x
cd v8x
uv sync
uv run v8x --help
```

### Authenticate

```bash
v8x login
v8x whoami
```

### Register a Local Cloud Account

Local deployment applications use cloud accounts too. A Multipass single-node Slurm deployment uses the `on_prem` provider:

```bash
v8x cloud account create local-multipass --provider on_prem
v8x cloud account list
```

### Create a Multipass Single-Node Slurm Cluster

```bash
v8x cluster create my-slurm-multipass-cluster \
  --cloud-account local-multipass \
  --app slurm-multipass \
  --options operating_system=rockylinux9,cpu=4,mem=8,disk=128G
```

Supported Multipass operating system choices are `rockylinux9`, `rockylinux10`, `noble`, and `resolute`.

### Create an LXD Cloud Account

LXD deployments require a cloud account with the LXD server URL and trust token:

```bash
v8x cloud account create local-lxd --provider lxd \
  --attributes '{"lxd_server_url":"https://127.0.0.1:8443","lxd_token":"<token>"}'
```

The current built-in LXD deployment applications are visible with:

```bash
v8x app list
```

### Next Steps

- [Installation Guide](./installation) - Install and verify `v8x`
- [Commands Reference](./commands) - Complete command reference
- [Private Installation Configuration](./private-vantage-installation) - Partner Vantage profile configuration
- [Deployment Applications](./deployment-applications) - Local deployment workflows
- [Storage Commands](./storage-import-expose) - PVCs, storage imports, and exposes
- [Usage Examples](./usage) - Practical command patterns
- [Architecture](./architecture) - Internals and module layout
- [Troubleshooting](./troubleshooting) - Common issues and solutions