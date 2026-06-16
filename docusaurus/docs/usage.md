---
title: Usage Examples
description: Practical examples of using v8x
---

## 1. Authenticate

Install and verify the CLI first with the [Installation Guide](./installation).

```bash
v8x login
v8x whoami
v8x token --decode
```

Add `--json` when you need automation-friendly output:

```bash
v8x whoami --json | jq '.identity.email'
```

## 2. Cloud Accounts

Cloud accounts are the current deployment target abstraction. Create them with `v8x cloud account create`, then pass the account name or ID to `v8x cluster create`.

```bash
# Local Multipass / on-prem-style account
v8x cloud account create local-multipass --provider on_prem

# LXD account with provider attributes
v8x cloud account create local-lxd --provider lxd \
  --attributes '{"lxd_server_url":"https://127.0.0.1:8443","lxd_token":"<token>"}'

# AWS account
v8x cloud account create aws-prod --provider aws \
  --attributes '{"role_arn":"arn:aws:iam::123456789012:role/VantageRole","region":"us-east-1"}'

# GCP account
v8x cloud account create gcp-dev --provider gcp \
  --attributes '{"project_id":"my-project","region":"us-central1"}'

# List registered accounts
v8x cloud account list --json | jq '.[] | {name, provider}'
```

Valid provider values are `aws`, `gcp`, `azure`, `on_prem`, `lxd`, and `microk8s`.

## 3. Cluster Management

```bash
# List clusters
v8x cluster list
v8x cluster list --json | jq '.clusters | length'

# Create a regular cluster from a cloud account name
v8x cluster create prod-hpc --cloud-account aws-prod

# Create a cluster from a cloud account ID
v8x cluster create prod-hpc-2 --cloud-account-id 16

# Create a local Multipass Slurm cluster
v8x cluster create compute-multipass-00 \
  --cloud-account local-multipass \
  --app slurm-multipass \
  --options operating_system=rockylinux9,cpu=4,mem=8,disk=128G

# Supported Multipass operating systems
# rockylinux9, rockylinux10, noble, resolute

# Get specific cluster details
v8x cluster get compute-multipass-00 --json | jq '.cluster | {name,id,status}'
```

## 4. Deployment Applications

```bash
# List bundled deployment applications
v8x app list

# Inspect recorded local deployments
v8x app deployment list
v8x app deployment get <deployment-id>

# Delete a recorded deployment and clean up associated local resources
v8x app deployment delete <deployment-id> --force
```

Current built-in local applications include `slurm-multipass` for `on_prem` and `vantage-system` / `juju-ext` for `lxd`.

## 5. Network and Storage

```bash
# Create a PersistentVolumeClaim in a cluster namespace
v8x storage create data-vol prod-hpc --namespace alice --size 100Gi

# List PVCs
v8x storage list prod-hpc --namespace alice --json | jq '.items[] | {name, status}'

# Create a network
v8x network create cluster-net --cidr 10.0.0.0/16

# List networks
v8x network list --json | jq '.networks[] | {name, cidr}'
```

## 6. Job Management Workflow

```bash
# Create a reusable script record
v8x job script create analysis --script-type bash --description "Run analysis workflow"

# Create a template record
v8x job template create --name gpu-analysis --description "GPU analysis template"

# Submit a job with SBATCH arguments
v8x job submission create \
  --name myjobsubmission \
  --job-script-id 123 \
  --client-id compute-multipass-00 \
  --execution-directory /home/ubuntu/jobs \
  --sbatch-arg "--partition=compute" \
  --sbatch-arg "--time=00:30:00"

# Monitor job status
v8x job submission get 789 --json | jq '.status'
```

For richer template or submission payloads, pass `--json-file ./payload.json` to the template or submission create command.

## 7. Team Collaboration

```bash
# Create team
v8x team create ml-research --description "ML Research Team"

# Add team members
v8x team add-member ml-research alice@company.com
v8x team add-member ml-research bob@company.com

# Set team roles separately when needed
v8x team set-role ml-research alice@company.com admin

# List team members
v8x team list-members ml-research
```

## 8. Profiles

```bash
v8x profile list
v8x profile create staging --vantage-url https://app.staging.vantagecompute.ai
v8x profile use staging
v8x login --profile staging
```

Use `--profile <name>` on any command to target a specific environment.

## 9. Piping and Automation

```bash
# Email of current authenticated user
auth_email=$(v8x whoami --json | jq -r '.identity.email')
echo "Authenticated as: $auth_email"

# Collect cluster names into a shell array
mapfile -t clusters < <(v8x cluster list --json | jq -r '.clusters[].name')
printf 'Found %d clusters\n' "${#clusters[@]}"

# Summarize clusters
v8x cluster list --json | jq '{count: (.clusters | length), names: [.clusters[].name]}'
```

## 10. Handling Errors

Add `-v` to surface debug logs:

```bash
v8x whoami -v
```

If tokens are expired, the CLI attempts a refresh. If refresh fails, run `v8x login` again.

---

See also: [Commands](./commands) | [Troubleshooting](./troubleshooting)