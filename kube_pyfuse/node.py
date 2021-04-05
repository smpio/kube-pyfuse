import datetime
import threading
import functools

import cachetools.func

from .kube import kube
from utils.kubernetes.watch import KubeWatcher, WatchEventType


UNKNOWN = type('UNKNOWN', (), {})()
GLOBAL_PSEUDO_NAMESPACE = '_'
CORE_RESOURCE_GROUP_NAME = '_'


class Node:
    is_dir = UNKNOWN
    name = UNKNOWN

    # implement only if is_dir=True
    def get_children(self):
        raise NotImplementedError

    # implement only if is_dir=False
    def read(self):
        raise NotImplementedError

    def get_stat(self):
        return {}


class RootNode(Node):
    is_dir = True
    name = '/'

    def __init__(self):
        self.children = [NamespaceNode(None), EmptyFileNode('.metadata_never_index')]
        self.update_thread = RootNodeUpdateThread(self)
        self.update_thread.start()

    def get_children(self):
        return self.children


class RootNodeUpdateThread(threading.Thread):
    def __init__(self, node):
        super().__init__(daemon=True)
        self.node = node

    def run(self):
        for event_type, ns in KubeWatcher(kube.v1.list_namespace):
            if event_type == WatchEventType.ADDED:
                self.node.children.append(NamespaceNode(ns))
            elif event_type == WatchEventType.DELETED:
                def matches(node):
                    if not isinstance(node, NamespaceNode):
                        return False
                    if not node.namespace:
                        return False
                    return ns.metadata.name == node.namespace.metadata.name
                self.node.children = [c for c in self.node.children if not matches(c)]


class NamespaceNode(Node):
    is_dir = True

    def __init__(self, namespace):
        self.namespace = namespace

    @property
    def name(self):
        if self.namespace:
            return self.namespace.metadata.name
        else:
            return GLOBAL_PSEUDO_NAMESPACE

    @functools.cache
    def get_children(self):
        if self.namespace:
            resource_groups = kube.namespaced_resources
        else:
            resource_groups = kube.global_resources

        children = []
        for resource_group_name, resources in resource_groups.items():
            if not resource_group_name:
                resource_group_name = CORE_RESOURCE_GROUP_NAME
            children.append(ResourceGroupNode(resource_group_name, resources, self.namespace))

        return children

    def get_stat(self):
        if not self.namespace:
            return super().get_stat()

        ctime = int(self.namespace.metadata.creation_timestamp.timestamp())
        return {
            'st_ctime': ctime,
            'st_mtime': ctime,
        }


class ResourceGroupNode(Node):
    is_dir = True

    def __init__(self, name, resources, namespace):
        self.name = name
        self.resources = resources
        self.namespace = namespace

    @functools.cache
    def get_children(self):
        children = []
        for kind, resource in self.resources.items():
            children.append(KindNode(resource, self.namespace))
        return children


class KindNode(Node):
    is_dir = True

    def __init__(self, resource, namespace):
        self.resource = resource
        self.namespace = namespace

    @property
    def name(self):
        return self.resource.kind

    @cachetools.func.ttl_cache(ttl=3)
    def get_children(self):
        children = []
        ns_name = self.namespace.metadata.name if self.namespace else None
        for item in kube.get_resource(self.resource, ns_name)['items']:
            children.append(ObjectNode(item))
        return children


class ObjectNode(Node):
    is_dir = False

    def __init__(self, obj):
        self.obj = obj

    @property
    def name(self):
        return self.obj['metadata']['name'] + '.yaml'

    @cachetools.func.ttl_cache(ttl=3)
    def read(self):
        text = kube.get_url(self.obj['metadata']['selfLink'], content_type='application/yaml')
        return text.encode('utf8')

    def get_stat(self):
        stat = {
            'st_size': len(self.read()),
        }

        ctime_iso = self.obj['metadata'].get('creationTimestamp')
        if ctime_iso:
            ctime = _time_iso2posix(self.obj['metadata']['creationTimestamp'])
            stat['st_ctime'] = ctime
            stat['st_mtime'] = ctime

        return stat


class EmptyFileNode(Node):
    is_dir = False

    def __init__(self, name):
        self.name = name

    def read(self):
        return b''


def _time_iso2posix(iso):
    iso = iso.replace('Z', '+00:00')
    dt = datetime.datetime.fromisoformat(iso)
    return int(dt.timestamp())
