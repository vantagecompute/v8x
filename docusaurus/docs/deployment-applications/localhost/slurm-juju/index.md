---
title: Charmed HPC Slurm Cluster (Juju)
description: Deploy a full Charmed HPC Slurm cluster into an existing Juju model with slurm-juju
---

The `slurm-juju` deployment application deploys a **complete Charmed HPC Slurm cluster** — the
[vantage-slurm-charm-operators](https://github.com/vantagecompute/vantage-slurm-charm-operators)
Topology‑A bundle — into an **existing Juju model**, then wires the single Vantage secret the cluster
needs. Unlike [`slurm-multipass`](../multipass) (a single VM) or the
[LXD/Juju extension apps](../charmed-hpc), `slurm-juju` brings up the full control plane, compute,
accounting, identity, shared storage, and observability as Juju applications.

`slurm-juju` does **no Juju provisioning**. It assumes you already have a bootstrapped controller and
a model; it only runs `juju deploy` plus the post‑deploy secret steps. It targets the controller and
model you name in `--options`.

## What it deploys

A single `juju deploy` of the bundle brings up ~18 applications and their relations, including:

| Role | Applications |
|---|---|
| Control plane | `slurmctld`, `slurmdbd`, `slurmrestd`, `sackd` (login) |
| Compute | `slurmd` (scale with `juju add-unit slurmd -n <N>`) |
| Accounting | `mysql` |
| Identity | `sssd` (SSSD against Vantage LDAP, on every Slurm node) |
| Vantage integration | `vantage-agent` (auth proxy + tunnel + OIDC/JWKS) |
| Shared storage | `nfs-data` / `nfs-srv` / `nfs-home` servers + `fs-data` / `fs-srv` / `fs-home` mounts |
| Observability | `monitoring` (Prometheus + Grafana), `node-exporter`, `slurm-job-exporter` |
| Containers | `apptainer` |

The applications above are deployed under these short names; each pulls its corresponding
`vantage-*` charm from Charmhub (e.g. the `slurmctld` application uses the `vantage-slurmctld` charm).

Charms are pulled from Charmhub on the `edge` channel — nothing is built locally. See the upstream
[deployment guide](https://github.com/vantagecompute/vantage-slurm-charm-operators/blob/main/docusaurus/docs/deployment.md)
and [architecture](https://github.com/vantagecompute/vantage-slurm-charm-operators/blob/main/docusaurus/docs/architecture.md)
for the full topology.

## Prerequisites

`slurm-juju` deploys into infrastructure you provide. Before you start you need:

- The **`juju` CLI** installed (it is a strictly‑confined snap — see [Troubleshooting](#troubleshooting)):
  ```bash
  sudo snap install juju
  juju version
  ```
- A **bootstrapped controller and an existing model** on a cloud that supports VM constraints (the
  bundle constrains Slurm/NFS units to `virt-type=virtual-machine`). For a local sandbox on LXD:
  ```bash
  sudo snap install lxd --channel latest/stable
  sudo lxd init --auto
  juju bootstrap localhost local        # controller named "local"
  juju add-model v8x-1                   # model named "v8x-1"
  ```
- **Charmhub reachable** from the machine running `v8x` (charms resolve from `edge`).
- `v8x` installed and authenticated, and an `on_prem` cloud account.

:::note slurm-juju never provisions Juju
It will not bootstrap a controller or create a model. If the controller or model named in
`--options` does not exist, the deploy fails fast — create them first with `juju bootstrap` /
`juju add-model`.
:::

## Create the cloud account

```bash
v8x cloud account create local-juju --provider on_prem
v8x cloud account list --provider on_prem
```

## Deploy Slurm

Point `slurm-juju` at the controller and model you bootstrapped:

```bash
v8x cluster create charmed-hpc-dev \
  --cloud-account local-juju \
  --app slurm-juju \
  --options controller=local,model=v8x-1
```

The `--options` flag for `slurm-juju` is a comma‑separated list. Both keys are **required**:

| Key | Required | Purpose |
|---|---|---|
| `controller` | yes | Name of an existing Juju controller (valid juju name: lowercase letters, digits, hyphens) |
| `model` | yes | Name of an existing Juju model on that controller |

Together they form the `juju -m controller:model` target for every command.

:::note Roadmap
A `slurmd-units=<N>` option to scale compute at deploy time is planned but **not yet implemented**.
For now, scale after deploy with `juju add-unit slurmd -n <N>`.
:::

## What happens under the hood

`slurm-juju` reproduces the upstream
[deployment runbook](https://github.com/vantagecompute/vantage-slurm-charm-operators/blob/main/docusaurus/docs/deployment.md)
automatically:

1. **Verifies the `juju` binary** is on `PATH` (aborts with install guidance if not).
2. **Renders the bundle.** The only value injected is the `sssd` application's `ldap-uri`, derived from your
   active profile's `vantage_url` (the first hostname label is swapped for `openldap`), e.g.
   `https://app.dev.vantagecompute.ai` → `ldaps://openldap.dev.vantagecompute.ai:636`.
3. **Deploys** the bundle into the target model: `juju deploy -m controller:model <bundle>`.
4. **Creates and wires the `vantage-cluster` secret** — the one required post‑deploy step. v8x does
   this for you (you never run `juju add-secret` by hand). It carries five keys, all sourced from the
   Vantage cluster + your settings:

   | Secret key | Source |
   |---|---|
   | `vantage-url` | your profile's `vantage_url` |
   | `client-id` | cluster OIDC client id |
   | `client-secret` | cluster OIDC client secret |
   | `org-id` | your organization id |
   | `ldap-bind-password` | cluster SSSD bind password |

   The secret is granted to `vantage-agent` and `sssd`, and `vantage-secret=<secret-id>` is set
   on both. From there the agent configures itself and SSSD renders `sssd.conf`; slurmrestd, Grafana,
   and Prometheus targets are wired by relation (no extra config).

## Inspect the deployment

```bash
v8x cluster get charmed-hpc-dev
v8x app deployment list

# Watch the cluster converge (Slurm installs from a tarball; first convergence takes a few minutes)
juju status -m local:v8x-1 --watch 5s

# Confirm Slurm sees the compute node
juju exec -m local:v8x-1 --unit slurmctld/0 -- sinfo
```

## Access Slurm

```bash
# SSH to the login node
juju ssh -m local:v8x-1 sackd/0

# Submit a quick job
srun -p slurmd hostname
```

## Delete the deployment

Removal tears down the bundle's applications **and** the `vantage-cluster` secret, but leaves the Juju
model intact (it does not destroy the model it deployed into):

```bash
v8x app deployment list                       # find the deployment id
v8x app deployment delete <deployment-id> --force
```

Or remove via the cluster record:

```bash
v8x cluster delete charmed-hpc-dev --cluster-type slurm --app slurm-juju --force
```

## Troubleshooting

```bash
juju version
juju models                                   # confirm the controller/model exist
juju status -m <controller>:<model>
juju debug-log -m <controller>:<model>
```

**`Juju Required` / `juju CLI not found`** — install the binary: `sudo snap install juju`.

**`controller/model not found`** — `slurm-juju` does not create them. Run `juju bootstrap` and
`juju add-model`, then re‑run with matching `--options controller=,model=`.

:::warning `no charm was found at "<path>"` or `permission denied` on deploy
This is **Juju snap confinement**, not a v8x bug. The `juju` CLI is a strictly‑confined snap: it
**cannot read the host `/tmp`** (the snap has a private `/tmp`) nor **hidden dot‑directories** under
your home (e.g. `~/.v8x`, `~/.cache`). v8x already works around this by writing the temporary bundle
to a **non‑hidden** directory under `$HOME`. If you hand `juju deploy` a path yourself, keep it out of
`/tmp` and out of dot‑dirs.
:::

**Charms fail to resolve** — confirm Charmhub is reachable and the `vantage-*` charms are published on
`edge`. The bundle pins charms to the `edge` channel.

**The secret looks half‑applied after a failed deploy** — `juju add-secret` is not idempotent. Clear
it before retrying, or remove the deployment (which also removes the secret):

```bash
juju remove-secret -m <controller>:<model> vantage-cluster
```

Re‑run any deploy with `-v` for verbose output:

```bash
v8x cluster create charmed-hpc-dev --cloud-account local-juju --app slurm-juju \
  --options controller=local,model=v8x-1 -v
```

## Next steps

- [Usage Examples](../../../usage.md)
- [Troubleshooting](../../../troubleshooting.md)
- [vantage-slurm-charm-operators documentation](https://github.com/vantagecompute/vantage-slurm-charm-operators)
