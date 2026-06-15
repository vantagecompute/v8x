---
title: MicroK8s Local Cloud Account
description: Register and use a local MicroK8s substrate with v8x
---

MicroK8s provides a local Kubernetes substrate. The current `v8x` CLI supports `microk8s` as a cloud account provider, but no built-in MicroK8s deployment application is listed by `v8x app list` in this version.

## Prerequisites

```bash
sudo snap install microk8s --channel 1.29/stable --classic
sudo microk8s.enable hostpath-storage
sudo microk8s.enable dns
sudo microk8s.enable metallb:10.64.140.43-10.64.140.49
sudo usermod -a -G microk8s "$USER"
sudo chown -f -R "$USER" ~/.kube
newgrp microk8s
```

Verify access:

```bash
microk8s status
microk8s kubectl get nodes
```

## Register the Cloud Account

```bash
v8x cloud account create local-microk8s --provider microk8s
v8x cloud account list --provider microk8s
```

## Create or Inspect Clusters

Use the account name or ID with cluster commands:

```bash
v8x cluster create microk8s-dev --cloud-account local-microk8s --cluster-type k8s
v8x cluster get microk8s-dev
```

If your installed version adds MicroK8s deployment applications, they will appear in:

```bash
v8x app list
```

Then pass the app name with `--app <app-name>` during `v8x cluster create`.

## Kubernetes Operations

Use MicroK8s directly for Kubernetes-level inspection:

```bash
microk8s kubectl get all --all-namespaces
microk8s kubectl get pv,pvc --all-namespaces
microk8s kubectl describe pod <pod-name> -n <namespace>
microk8s kubectl logs <pod-name> -n <namespace>
```

## Troubleshooting

```bash
microk8s status
microk8s inspect
microk8s kubectl get nodes -o wide
v8x cluster create microk8s-dev --cloud-account local-microk8s --cluster-type k8s -v
```

Common issues are missing MicroK8s group membership, disabled storage or DNS addons, and MetalLB address ranges that conflict with your local network.