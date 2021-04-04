import stat
import errno

import fuse
import kubernetes


GLOBAL_PSEUDO_NAMESPACE = '_'
CORE_RESOURCE_GROUP_NAME = '_'


class NodeError(Exception):
    def __init__(self, my_errno):
        super().__init__(my_errno)
        self.my_errno = my_errno


class Node:
    is_dir = None

    def __init__(self, path_parts, kube):
        self.path_parts = path_parts
        self.kube = kube

    def readdir(self):
        raise NodeError(errno.EACCES)

    def getattr(self):
        if self.is_dir is None:
            raise -errno.EACCES

        st = fuse.Stat()
        if self.is_dir:
            st.st_mode = stat.S_IFDIR | 0o755
            st.st_nlink = 2
        else:
            st.st_mode = stat.S_IFREG | 0o444
            st.st_nlink = 1
        return st

    def open(self, flags):
        return -errno.EACCES

    def read(self, size, offset):
        return -errno.EACCES

    def _get_resource_groups(self, namespace):
        if namespace == GLOBAL_PSEUDO_NAMESPACE:
            resources = self.kube.global_resources
        else:
            resources = self.kube.namespaced_resources
            try:
                self.kube.v1.read_namespace(namespace)
            except kubernetes.client.exceptions.ApiException as err:
                if err.status == 404:
                    raise NodeError(errno.ENOENT) from err
                else:
                    raise err
        return resources

    def _get_resources(self, namespace, resource_group_name):
        resource_groups = self._get_resource_groups(namespace)
        if resource_group_name == CORE_RESOURCE_GROUP_NAME:
            resource_group_name = ''
        try:
            return resource_groups[resource_group_name]
        except KeyError as err:
            raise NodeError(errno.ENOENT) from err


class RootNode(Node):
    is_dir = True

    def readdir(self):
        yield fuse.Direntry(GLOBAL_PSEUDO_NAMESPACE)
        result = self.kube.v1.list_namespace()
        for ns in result.items:
            yield fuse.Direntry(ns.metadata.name)


class NamespaceNode(Node):
    is_dir = True

    def readdir(self):
        namespace = self.path_parts[-1]
        resource_groups = self._get_resource_groups(namespace)
        for resource_group_name in resource_groups.keys():
            if not resource_group_name:
                resource_group_name = CORE_RESOURCE_GROUP_NAME
            yield fuse.Direntry(resource_group_name)


class ResourceGroupNode(Node):
    is_dir = True

    def readdir(self):
        namespace = self.path_parts[-2]
        resource_group_name = self.path_parts[-1]
        resources = self._get_resources(namespace, resource_group_name)

        for kind in resources.keys():
            yield fuse.Direntry(kind)


class KindNode(Node):
    is_dir = True

    def readdir(self):
        namespace = self.path_parts[-3]
        resource_group_name = self.path_parts[-2]
        kind = self.path_parts[-1]
        resources = self._get_resources(namespace, resource_group_name)

        try:
            resource = resources[kind]
        except KeyError as err:
            raise NodeError(errno.ENOENT) from err

        for item in self.kube.get_resource(resource, namespace)['items']:
            yield fuse.Direntry(item['metadata']['name'] + '.yaml')


class ObjectNode(Node):
    is_dir = False
