---
title: Storage Commands
description: CLI commands for PVCs, storage systems, imports, and exposes
---

# Storage Commands

`v8x storage` manages cluster PersistentVolumeClaims, storage system registrations, imports, and external exposes.

```text
v8x storage
├── create          Create a PersistentVolumeClaim
├── delete          Delete a PersistentVolumeClaim
├── get             Get PersistentVolumeClaim details
├── list            List PersistentVolumeClaims
├── list-available  List available StorageClasses
├── system          Manage storage system registrations
├── import          Import storage into namespaces
└── expose          Expose cluster storage to external clients
```

Most storage commands take the cluster name as a positional argument. Use `--namespace` when the target namespace is not the default derived from your login.

## PersistentVolumeClaims

### Create a PVC

```bash
v8x storage create <name> <cluster-name> \
  --namespace <namespace> \
  --size 100Gi \
  --storage-class <storage-class> \
  --access-mode ReadWriteOnce
```

Example:

```bash
v8x storage create data-vol prod-cluster \
  --namespace alice \
  --size 100Gi \
  --storage-class rook-cephfs
```

### Inspect PVCs

```bash
v8x storage list prod-cluster --namespace alice
v8x storage get data-vol prod-cluster --namespace alice
v8x storage list-available prod-cluster
```

### Delete a PVC

```bash
v8x storage delete data-vol prod-cluster --namespace alice --force
```

## Storage Systems

Storage systems register backing storage infrastructure such as CephFS or CephNFS.

### Create a Storage System

```bash
v8x storage system create <name> <cluster-name> <system-type> <storage-class-name> \
  --namespace vantage-rook-ceph \
  --description "Shared CephFS" \
  --config-json '{"key":"value"}'
```

Example:

```bash
v8x storage system create shared-ceph prod-cluster cephfs rook-cephfs \
  --namespace vantage-rook-ceph
```

### Manage Storage Systems

```bash
v8x storage system list prod-cluster
v8x storage system get shared-ceph prod-cluster --namespace vantage-rook-ceph
v8x storage system update shared-ceph prod-cluster --config-json '{"replicas":2}'
v8x storage system delete shared-ceph prod-cluster --force
```

## Storage Imports

Imports make external or cross-namespace storage available as PVCs.

### NFS Import

```bash
v8x storage import nfs create datasets prod-cluster nas01.internal /exports/ml-datasets \
  --namespace alice \
  --capacity 1Ti \
  --access-mode ReadWriteMany
```

### CephFS Import

```bash
v8x storage import cephfs create shared-ceph prod-cluster shared-storage vantage-system \
  --namespace alice \
  --capacity 500Gi
```

### Internal Cross-Namespace Import

```bash
v8x storage import internal create shared-storage prod-cluster shared-storage vantage-system \
  --namespace alice \
  --capacity 500Gi \
  --access-mode ReadWriteMany
```

### Shared Import Commands

```bash
v8x storage import list prod-cluster --namespace alice --storage-type nfs
v8x storage import get datasets prod-cluster --namespace alice --storage-type nfs
v8x storage import delete datasets prod-cluster --namespace alice --storage-type nfs --force
```

The `--storage-type` option defaults to `nfs` for shared import commands.

## External Exposes

Expose commands make in-cluster storage reachable from clients outside the Kubernetes cluster.

### CephFS External Expose

```bash
v8x storage expose cephfs create external-cephfs prod-cluster \
  --ceph-client-name external-cephfs \
  --ceph-mds-path /volumes/csi \
  --ceph-osd-pool vantage-cephfs-data \
  --monitor-service-type NodePort
```

Manage the expose:

```bash
v8x storage expose cephfs get external-cephfs prod-cluster
v8x storage expose cephfs list prod-cluster
v8x storage expose cephfs status external-cephfs prod-cluster
v8x storage expose cephfs mount-commands external-cephfs prod-cluster
v8x storage expose cephfs credentials external-cephfs prod-cluster
v8x storage expose cephfs delete external-cephfs prod-cluster --force
```

### NFS External Expose

```bash
v8x storage expose nfs create external-nfs prod-cluster shared-storage alice
v8x storage expose nfs get external-nfs prod-cluster
v8x storage expose nfs delete external-nfs prod-cluster --force
```

## Common Options

| Option | Description |
|---|---|
| `--namespace` | Target namespace for PVCs and imports |
| `--json`, `-j` | Output in JSON format |
| `--verbose`, `-v` | Enable verbose terminal output |
| `--profile`, `-p` | Profile name to use |
| `--force` | Skip confirmation prompts on delete commands |

## Notes

- Namespaces default to the namespace derived from your authenticated user when supported by the command.
- Storage import commands are grouped by storage type: `nfs`, `cephfs`, and `internal`.
- Only resources managed by Vantage storage commands should be deleted through this interface.