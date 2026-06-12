---
title: Storage Commands
description: CLI commands for managing storage systems, importing storage, and exposing cluster storage
---

# Storage Commands

The v8x provides a hierarchical command structure for managing storage:

```
v8x storage
├── system        # Manage storage system deployments (CephNFS, etc.)
├── import        # Import storage into cluster namespaces
│   ├── nfs       # NFS-specific import commands
│   ├── cephfs    # CephFS-specific import commands
│   └── internal  # Cross-namespace PVC imports
├── expose        # Expose cluster storage to external clients
│   ├── cephfs    # CephFS external expose commands
│   └── nfs       # NFS external expose commands
├── create        # Create a PVC
├── delete        # Delete a PVC
├── get           # Get PVC details
├── list          # List PVCs
└── list-available # List available storage classes
```

---

## Storage System Commands

Manage storage system deployments (CephNFS, CephFS infrastructure, etc.).

### Create a Storage System

```bash
v8x storage system create <name> \
  --cluster <cluster> \
  --type <system-type> \
  [--namespace <ns>] \
  [--config-json '{"key": "value"}']
```

**Example — deploy a CephNFS system:**

```bash
v8x storage system create my-nfs \
  --cluster prod-cluster \
  --type cephnfs \
  --namespace vantage-rook-ceph
```

### Get Storage System Details

```bash
v8x storage system get <name> --cluster <cluster>
```

### List All Storage Systems

```bash
v8x storage system list --cluster <cluster>
```

### Update a Storage System

```bash
v8x storage system update <name> \
  --cluster <cluster> \
  --config-json '{"server_count": 2}'
```

### Delete a Storage System

```bash
v8x storage system delete <name> --cluster <cluster> [--force]
```

---

## Import Commands

Import storage into cluster namespaces. Organised by storage type.

### NFS Import

#### Create NFS Import

```bash
v8x storage import nfs create <pvc-name> \
  --cluster <cluster> \
  --nfs-server <hostname-or-ip> \
  --nfs-share <export-path> \
  [--namespace <ns>] \
  [--capacity 100Gi] \
  [--access-mode ReadWriteMany] \
  [--read-only]
```

**Example:**

```bash
v8x storage import nfs create datasets \
  --cluster prod-cluster \
  --nfs-server nas01.internal \
  --nfs-share /exports/ml-datasets \
  --capacity 1Ti
```

#### Create External NFS Import

Import an NFS server from outside the cluster:

```bash
v8x storage import nfs create-external <name> \
  --cluster <cluster> \
  --nfs-server <hostname-or-ip> \
  --nfs-share <export-path> \
  --namespace <ns> \
  [--capacity 100Gi] \
  [--access-mode ReadWriteMany]
```

### CephFS Import

#### Create CephFS Import

```bash
v8x storage import cephfs create <pvc-name> \
  --cluster <cluster> \
  --source-pvc <source-pvc-name> \
  --source-namespace <source-ns> \
  [--namespace <ns>] \
  [--capacity 100Gi]
```

**Example:**

```bash
v8x storage import cephfs create shared-ceph \
  --cluster prod-cluster \
  --source-pvc shared-storage \
  --source-namespace vantage-system
```

#### Create External CephFS Import

Import from an external (non-Rook) Ceph cluster:

```bash
v8x storage import cephfs create-external <name> \
  --cluster <cluster> \
  --ceph-monitors "10.0.0.1:6789,10.0.0.2:6789" \
  --ceph-client <client-name> \
  --ceph-client-key "AQD...==" \
  --ceph-fs-name <fs-name> \
  [--ceph-root-path /] \
  --namespace <ns> \
  [--capacity 500Gi]
```

### Internal (Cross-Namespace) Import

Expose an existing PVC to another namespace:

#### Create Cross-Namespace Import

```bash
v8x storage import internal create <target-pvc-name> \
  --cluster <cluster> \
  --source-pvc <source-pvc> \
  --source-namespace <source-ns> \
  [--namespace <target-ns>] \
  [--capacity 100Gi] \
  [--access-mode ReadWriteMany] \
  [--read-only]
```

**Example — expose shared-storage to your namespace:**

```bash
v8x storage import internal create shared-storage \
  --cluster prod-cluster \
  --source-pvc shared-storage \
  --source-namespace vantage-system \
  --capacity 500Gi
```

#### Get / List / Delete Cross-Namespace Imports

```bash
v8x storage import internal get <pvc-name> --cluster <cluster> [--namespace <ns>]
v8x storage import internal list --cluster <cluster> [--namespace <ns>]
v8x storage import internal delete <pvc-name> --cluster <cluster> [--namespace <ns>] [--force]
```

### Shared Import Commands

These commands operate across all import types (NFS, CephFS, internal):

```bash
# Get details of any import
v8x storage import get <pvc-name> --cluster <cluster> [--namespace <ns>]

# List all imports in a namespace
v8x storage import list --cluster <cluster> [--namespace <ns>]

# Delete any import
v8x storage import delete <pvc-name> --cluster <cluster> [--namespace <ns>] [--force]

# External import lifecycle
v8x storage import get-external <name> --cluster <cluster>
v8x storage import list-external --cluster <cluster> [--namespace <ns>]
v8x storage import delete-external <name> --cluster <cluster> [--force]
v8x storage import external-status <name> --cluster <cluster>
v8x storage import external-mount-info <name> --cluster <cluster>
v8x storage import external-config <name> --cluster <cluster> [--json]
```

---

## Expose Commands

Expose cluster storage to clients **outside** the Kubernetes cluster.

### CephFS External Expose

```bash
# Create
v8x storage expose cephfs create <name> \
  --cluster <cluster> \
  [--ceph-client <client-name>] \
  [--mds-path /volumes/csi] \
  [--osd-pool vantage-cephfs-data] \
  [--expose-monitors] \
  [--monitor-service-type NodePort]

# Get details
v8x storage expose cephfs get <name> --cluster <cluster>

# List all
v8x storage expose cephfs list --cluster <cluster>

# Delete
v8x storage expose cephfs delete <name> --cluster <cluster> [--force]

# Get mount commands
v8x storage expose cephfs mount-commands <name> --cluster <cluster>

# Get credentials
v8x storage expose cephfs credentials <name> --cluster <cluster>

# Get status
v8x storage expose cephfs status <name> --cluster <cluster>
```

### NFS External Expose

```bash
# Create
v8x storage expose nfs create <name> \
  --cluster <cluster> \
  --source-pvc <pvc-name> \
  --source-namespace <ns>

# Get details
v8x storage expose nfs get <name> --cluster <cluster>

# Delete
v8x storage expose nfs delete <name> --cluster <cluster> [--force]
```

---

## Common Options

| Option | Description |
|---|---|
| `--cluster`, `-c` | Cluster name (required) |
| `--namespace`, `-n` | Target namespace (default: derived from your username) |
| `--json` | Output in JSON format |
| `--force`, `-f` | Skip confirmation prompt (delete commands) |

## Notes

- All operations are **idempotent** — re-importing or re-exposing the same storage returns the existing resource
- Namespaces are created automatically if they don't exist, with Istio sidecar injection enabled
- Only resources managed by Vantage (labeled with `app.kubernetes.io/managed-by=vantage-storage`) can be deleted through these commands
- The `--namespace` flag defaults to your user namespace derived from your login email
