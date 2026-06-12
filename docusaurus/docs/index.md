---
title: "v8x - The Vantage Compute CLI"
description: "Authenticate, manage profiles & clusters, deploy apps, and run GraphQL queries against Vantage Compute"
slug: /
---

## The unified command-line interface for Vantage Compute

v8x is a modern async Python tool that unifies authentication, profile management, cluster operations and GraphQL querying against the Vantage Compute platform.


### Quick Start

Install from pypi:

```bash
uv venv
source .venv/bin/activate

uv pip install v8x
```

Or from source:

```shell-session
git clone https://github.com/vantagecompute/v8x
cd v8x
uv sync
uv run v8x --help
```

#### Authenticate

Authenticate against the Vantage platform using the `login` command.

```bash
v8x login
```

#### Create a Multipass Singlenode Cluster

```bash
v8x cluster create my-slurm-multipass-cluster \
    --cloud localhost \
    --app slurm-multipass
```

#### Create a Slurm Cluster in LXD Containers using Juju

```bash
v8x cluster create my-slurm-lxd-cluster \
    --cloud localhost \
    --app slurm-juju-localhost
```

#### Create a Slurm Cluster on MicroK8S

```bash
v8x cluster create my-slurm-microk8s-cluster \
    --cloud localhost \
    --app slurm-microk8s-localhost
```

### Next Steps

- [Installation Guide](./installation) – Install & Configure
- [Commands Reference](./commands) – Complete Command Reference
- [Private Installation Configuration](./private-vantage-installation) – Partner Vantage Deployment CLI Profile Configuration
- [Notebooks](./notebooks) – Jupyterhub Notebook Server Lifecycle
- [Deployment Applications](./deployment-applications) – Slurm Deployment Automation
- [Usage Examples](./usage) – Practical Command Patterns
- [Architecture](./architecture) – Internals & Module Layout
- [Troubleshooting](./troubleshooting) – Common Issues and Solutions
