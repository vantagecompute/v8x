---
title: Usage Examples
description: Practical examples of using v8x
---

## 1. Install the v8x

Install `v8x` with `uv`:

```bash
uv venv
source .venv/bin/activate

uv pip install v8x
```

## 2. Vantage Login

```bash
v8x login
```

## 3. Cluster Management Commands

```bash
# List clusters (using alias)
v8x clusters
v8x clusters --json | jq '.clusters | length'

# Create new cluster using juju
v8x cluster create compute-juju-00 --cloud localhost --app slurm-juju-localhost

# Create new local vm singlenode cluster using multipass
v8x cluster create compute-multipass-00 --cloud localhost --app slurm-multipass

# Create new local vm singlenode cluster using microk8s
v8x cluster create compute-microk8s-00 --cloud localhost --app slurm-microk8s-localhost

# Get specific cluster
v8x cluster get compute-juju-00 --json | jq '.cluster | {name,id,status}'
```

## 4. Vantage Applications (apps)

```bash
# List available applications
v8x apps
```

## 5. Cloud Provider Management

```bash
# Add cloud providers
v8x cloud add aws-prod --provider aws
v8x cloud add gcp-dev --provider gcp
v8x cloud add compute-a-on-site-us-east --provider on-premises


# List configurations
v8x clouds --json | jq '.clouds[] | {name, provider, status}'

{
  "name": "aws-prod",
  "provider": "aws",
  "status": "active"
}
{
  "name": "gcp-dev",
  "provider": "gcp",
  "status": "active"
}
```

## 6. Network and Storage

```bash
# Create a storage volume
v8x storage create data-vol --size 100GB

# Create network
v8x network create cluster-net --cidr 10.0.0.0/16

# List resources
v8x storage list --json | jq '.volumes[] | {name, size, status}'
v8x networks --json | jq '.networks[] | {name, cidr}'
```

## 7. Job Management Workflow

```bash
# Create job script
v8x job script create analysis --file ./my_script.py

# Create job template for reuse
v8x job template create gpu-analysis \
  --memory 16GB --gpus 2 --queue gpu

# Submit job
v8x job submission create myjobsubmission \
  --script script-123 \
  --template template-456 \
  --priority high

# Monitor job status
v8x job submission get --id sub-789 --json | jq '.status'
```

## 8. Team Collaboration

```bash
# Create team
v8x team create ml-research --description "ML Research Team"

# Add team members
v8x team member add --team ml-research --user alice@company.com --role admin
v8x team member add --team ml-research --user bob@company.com --role member

# List team members
v8x team member list --team ml-research
```

## 9. Switch Profiles

```bash
v8x profile list
v8x profile create staging --activate
v8x login
```

## 6. GraphQL Query (Programmatic)

```python
import asyncio
from v8x.gql_client import create_async_graphql_client
from v8x.config import Settings
from v8x.auth import extract_persona

async def main():
    settings = Settings()
    persona = extract_persona("default")
    client = create_async_graphql_client(settings, "default")
    data = await client.execute_async("""query { __typename }""")
    print(data)

asyncio.run(main())
```

## 7. Token Cache Inspection

```python
from v8x.cache import load_tokens_from_cache
from v8x.schemas import TokenSet

tokens: TokenSet = load_tokens_from_cache("default")
print(tokens.access_token[:16] + "..." if tokens.access_token else "NO TOKEN")
```

## 8. Piping & Automation

```bash
# Email of current authenticated user
auth_email=$(v8x whoami --json | jq -r '.identity.email')

echo "Authenticated as: $auth_email"

# Collect cluster names into a shell array
mapfile -t clusters < <(v8x clusters list --json | jq -r '.clusters[].name')
printf 'Found %d clusters\n' "${#clusters[@]}"
```

## 9. Handling Errors

Add `-v` to surface debug logs:

```bash
vantage -v whoami
```

If tokens are expired the CLI will attempt a refresh; if that fails re-run `v8x login`.

## 10. JSON Extraction Template

```bash
v8x clusters --json | jq '{count: (.clusters | length), names: [.clusters[].name]}'
```

---
See also: [Commands](./commands) | [Troubleshooting](./troubleshooting)
