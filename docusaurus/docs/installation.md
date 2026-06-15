---
title: Installation Guide
description: Install v8x
---

## Installation

Install `v8x` from PyPI with `uv`:

```bash
uv tool install v8x
```

If you prefer an isolated virtual environment:

```bash
uv venv
source .venv/bin/activate
uv pip install v8x
```

Verify the install:

```bash
v8x version
v8x --help
```

## From Source

```bash
git clone https://github.com/vantagecompute/v8x
cd v8x
uv sync
uv run v8x version
```

Use `uv run v8x ...` for source-tree commands so the CLI uses the project-managed environment.