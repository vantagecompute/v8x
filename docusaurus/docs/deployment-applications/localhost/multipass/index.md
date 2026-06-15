---
title: Multipass Single-node Slurm Cluster
description: Deploy a single-node Slurm cluster using a Multipass virtual machine
---

The `slurm-multipass` deployment application creates a single-node Slurm environment in a Multipass virtual machine.

## Prerequisites

- Multipass installed and running
- Enough local resources for the VM
- `v8x` installed and authenticated

```bash
sudo snap install multipass
multipass version
v8x login
```

## Create the Cloud Account

```bash
v8x cloud account create local-multipass --provider on_prem
v8x cloud account list --provider on_prem
```

## Deploy Slurm

```bash
v8x cluster create slurm-multipass-dev \
  --cloud-account local-multipass \
  --app slurm-multipass \
  --options operating_system=rockylinux9,cpu=4,mem=8,disk=128G
```

The `--options` flag is a comma-separated list for `slurm-multipass` only:

| Key | Purpose |
|---|---|
| `operating_system` | One of `rockylinux9`, `rockylinux10`, `noble`, `resolute` |
| `cpu` | Number of VM CPUs |
| `mem` | Memory size in GiB |
| `disk` | Disk size, such as `128G` |

## Inspect the Deployment

```bash
v8x cluster get slurm-multipass-dev
v8x app deployment list
multipass list
```

Use the deployment ID from `v8x app deployment list` when you need the local deployment record:

```bash
v8x app deployment get <deployment-id>
```

## Access Slurm

```bash
multipass shell slurm-multipass-dev
sinfo
squeue
srun --nodes=1 --ntasks=1 hostname
```

If the VM name differs from the cluster name, check `multipass list` and use the VM name shown there.

## Delete the Deployment

You can delete the recorded deployment and clean up associated local resources:

```bash
v8x app deployment delete <deployment-id> --force
```

Or delete the cluster record and request app cleanup:

```bash
v8x cluster delete slurm-multipass-dev --cluster-type slurm --app slurm-multipass --force
```

For low-level VM cleanup, use Multipass directly:

```bash
multipass delete <vm-name> --purge
```

## Troubleshooting

```bash
multipass version
multipass list
multipass info <vm-name>
multipass logs <vm-name>
v8x cluster create slurm-multipass-dev --cloud-account local-multipass --app slurm-multipass -v
```

Common issues are usually local resource pressure, Multipass daemon startup problems, or an unsupported `operating_system` value.