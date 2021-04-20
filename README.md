# kube-pyfuse

FUSE based filesystem for Kubernetes cluster management.

Namespaces are represented as folders and objects as YAML manifests.
You can list, read, create, edit and delete every object in your cluster with maximum control.

## Usage

### macOS

Copy [local.kube-pyfuse.plist](./local.kube-pyfuse.plist) to `~/Library/LaunchAgents/local.kube-pyfuse.plist`. Replace UPPERCASE vars.
