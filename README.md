<div align="center">
<a href="https://www.vantagecompute.ai/">
  <img src="https://vantage-compute-public-assets.s3.us-east-1.amazonaws.com/branding/vantage-logo-text-black-horz.png" alt="Vantage Compute Logo" width="100" style="margin-bottom: 0.5em;"/>
</a>
</div>

<div align="center">

# v8x
A modern Python command-line interface for interacting with Vantage Compute.

[![License](https://img.shields.io/badge/license-GPLv3-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![PyPI](https://img.shields.io/pypi/v/v8x.svg)](https://pypi.org/project/v8x/)

![Build Status](https://img.shields.io/github/actions/workflow/status/vantagecompute/v8x/ci.yaml?branch=main&label=build&logo=github&style=plastic)
![GitHub Issues](https://img.shields.io/github/issues/vantagecompute/v8x?label=issues&logo=github&style=plastic)
![Pull Requests](https://img.shields.io/github/issues-pr/vantagecompute/v8x?label=pull-requests&logo=github&style=plastic)
![GitHub Contributors](https://img.shields.io/github/contributors/vantagecompute/v8x?logo=github&style=plastic)

</div>

## Overview

v8x provides a streamlined interface to authenticate with Vantage, discover and manage compute resources, and operate cloud or local environments from a single command surface.

Use the CLI for high-level workflows such as:

- logging in and managing profiles
- creating and managing clusters and deployments
- working with app, storage, and cloud account resources
- integrating Vantage operations into automation scripts and CI pipelines

## Getting Started

### Option 1: Install from PyPI

```bash
pip install v8x

v8x login
```

### Option 2: Install from Source

```bash
git clone https://github.com/vantagecompute/v8x.git
cd v8x
uv sync

uv run v8x login
```

## Deploy your First Slurm Cluster using a Multipass VM

1. Add a cloud account

```bash
uv run v8x cloud account create mydatacenter-west --provider on_prem
```

2. Create the cluster

```bash
uv run v8x cluster create slurm-multipass-demo-james \
  --app slurm-multipass \
  --cloud-account-name mydatacenter-west \
  --cluster-type slurm \
  --create-team
```

## Documentation

For full command reference, workflows, and operational guides, see:

- https://docs.vantagecompute.ai/v8x

## Support

- Issues: https://github.com/vantagecompute/v8x/issues
- Discussions: https://github.com/vantagecompute/v8x/discussions

## License

Copyright &copy; 2025 Vantage Compute Corporation

This project is licensed under the GPLv3 License. See [LICENSE](LICENSE) for details.

