---
title: Deployment Applications
description: Deployment application usage
---

Deployment applications are bundled automation modules that `v8x cluster create` can run after creating or resolving a cluster. They are selected with the `--app` option.

List the deployment applications available in your installed CLI:

```bash
v8x app list
```

The current built-in local applications are:

| App | Cloud | Substrate | Purpose |
|---|---|---|---|
| `slurm-multipass` | `on_prem` | `multipass` | Create a single-node Slurm cluster in Multipass |
| `vantage-system` | `lxd` | `lxd` | Provision Vantage System on an LXD-backed cluster |
| `juju-ext` | `lxd` | `juju` | Extend an LXD cluster with Juju-managed compute nodes |

The common flow is:

```bash
v8x cloud account create <account-name> --provider <provider> [--attributes '<json>']
v8x cluster create <cluster-name> --cloud-account <account-name> --app <app-name>
v8x app deployment list
```

Choose a substrate-specific guide to continue:

- [Localhost Deployment Applications](./deployment-applications/localhost)
- [Multipass Single-node Slurm](./deployment-applications/localhost/multipass)
- [LXD and Juju](./deployment-applications/localhost/charmed-hpc)
- [MicroK8s Local Cloud Accounts](./deployment-applications/localhost/microk8s)