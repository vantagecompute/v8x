---
title: Localhost Deployment Applications
description: Deployment applications for localhost sandboxes
---

Localhost deployment applications let you exercise Vantage workflows on a laptop or development machine. The current CLI still models these targets as cloud accounts, so create a cloud account first and then pass it to `v8x cluster create`.

## Multipass

Use [Multipass](https://canonical.com/multipass) to launch a single-node Slurm virtual machine.

```bash
sudo snap install multipass
multipass version
v8x cloud account create local-multipass --provider on_prem
v8x cluster create slurm-dev \
  --cloud-account local-multipass \
  --app slurm-multipass \
  --options operating_system=rockylinux9,cpu=4,mem=8,disk=128G
```

Supported operating systems for `slurm-multipass` are `rockylinux9`, `rockylinux10`, `noble`, and `resolute`.

Continue to the [Multipass guide](./localhost/multipass).

## LXD and Juju

Use [LXD](https://canonical.com/lxd) and [Juju](https://canonical.com/juju) for LXD-backed Vantage System and Juju extension workflows.

```bash
sudo snap install lxd --channel latest/stable
sudo snap install juju --channel 3.6/stable
sudo lxd init --auto
sudo adduser "$USER" lxd
lxc network set lxdbr0 ipv6.nat false
juju bootstrap localhost
```

Create an LXD cloud account with the server URL and trust token:

```bash
v8x cloud account create local-lxd --provider lxd \
  --attributes '{"lxd_server_url":"https://127.0.0.1:8443","lxd_token":"<token>"}'
```

Continue to the [LXD and Juju guide](./localhost/charmed-hpc).

## Charmed HPC Slurm Cluster (Juju)

Use `slurm-juju` to deploy a full Charmed HPC Slurm cluster into an **existing** Juju controller and
model. It deploys the vantage-slurm-charm-operators bundle (control plane, compute, accounting,
identity, shared storage, and observability) and wires the required Vantage secret automatically.

```bash
sudo snap install juju
juju bootstrap localhost local
juju add-model v8x-1
v8x cloud account create local-juju --provider on_prem
v8x cluster create charmed-hpc-dev \
  --cloud-account local-juju \
  --app slurm-juju \
  --options controller=local,model=v8x-1
```

Continue to the [Charmed HPC (Juju) guide](./localhost/slurm-juju).

## MicroK8s

Use [MicroK8s](https://canonical.com/microk8s) when you want a local Kubernetes substrate.

```bash
sudo snap install microk8s --channel 1.29/stable --classic
sudo microk8s.enable hostpath-storage
sudo microk8s.enable dns
sudo microk8s.enable metallb:10.64.140.43-10.64.140.49
sudo usermod -a -G microk8s "$USER"
sudo chown -f -R "$USER" ~/.kube
newgrp microk8s
```

Register it as a cloud account:

```bash
v8x cloud account create local-microk8s --provider microk8s
```

Continue to the [MicroK8s guide](./localhost/microk8s).