---
title: LXD and Juju Deployment Applications
description: Deploy LXD-backed Vantage applications and Juju extensions on localhost
---

The current built-in LXD applications are `vantage-system` and `juju-ext`. Use `v8x app list` to confirm the exact names in your installed version.

## Prerequisites

```bash
sudo snap install lxd --channel latest/stable
sudo snap install juju --channel 3.6/stable
sudo lxd init --auto
sudo adduser "$USER" lxd
lxc network set lxdbr0 ipv6.nat false
juju bootstrap localhost
```

Log out and back in if your shell does not pick up the `lxd` group membership.

## Create the LXD Cloud Account

Generate or retrieve an LXD trust token, then register the account:

```bash
v8x cloud account create local-lxd --provider lxd \
  --attributes '{"lxd_server_url":"https://127.0.0.1:8443","lxd_token":"<token>"}'
```

## Deploy an LXD Application

```bash
# Provision Vantage System on LXD
v8x cluster create lxd-vantage-system \
  --cloud-account local-lxd \
  --app vantage-system

# Extend an LXD cluster with Juju-managed compute nodes
v8x cluster create lxd-juju-compute \
  --cloud-account local-lxd \
  --app juju-ext
```

## Inspect and Operate

```bash
v8x cluster list
v8x cluster get lxd-vantage-system
v8x app deployment list
lxc list
juju status
```

Cluster internals are operated with the substrate tools after deployment:

```bash
juju ssh <application>/<unit>
juju debug-log
lxc logs <instance-name>
```

## Delete

```bash
v8x app deployment delete <deployment-id> --force
v8x cluster delete lxd-vantage-system --cluster-type slurm --app vantage-system --force
```

Use `lxc list` and `juju status` after cleanup to confirm there are no leftover local resources.

## Next Steps

- [Usage Examples](../../../usage.md)
- [Troubleshooting](../../../troubleshooting.md)
- [Charmed HPC Documentation](https://charmed-hpc.readthedocs.io/)