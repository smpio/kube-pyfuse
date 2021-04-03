import os
import stat
import errno
from collections.abc import Iterable

import fuse

from .kube import Kube

fuse.fuse_python_api = (0, 2)


class KubeFS(fuse.Fuse):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.kube = Kube()

    def _path2node(self, path):
        path = path[1:]  # remove leading slash
        path_parts = path.split('/')

        if len(path_parts) == 1 and path_parts[0] == '':
            cls = RootNode
        elif len(path_parts) == 1:
            cls = NamespaceNode
        elif len(path_parts) == 2:
            cls = ResourceGroupNode
        elif len(path_parts) == 3:
            cls = ObjectNode
        else:
            cls = Node

        return cls(path_parts, self.kube)

    def readdir(self, path, offset):
        node = self._path2node(path)
        ret = node.readdir()
        if isinstance(ret, Iterable):
            yield fuse.Direntry('.')
            yield fuse.Direntry('..')
            yield from ret
        else:
            return ret

    def getattr(self, path):
        node = self._path2node(path)
        return node.getattr()

    def open(self, path, flags):
        node = self._path2node(path)
        return node.open(flags)

    def read(self, path, size, offset):
        node = self._path2node(path)
        return node.read(size, offset)


class Node:
    is_dir = None

    def __init__(self, path_parts, kube):
        self.path_parts = path_parts
        self.kube = kube

    def readdir(self):
        return -errno.EACCES

    def getattr(self):
        if self.is_dir is None:
            return -errno.EACCES

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


class RootNode(Node):
    is_dir = True

    def readdir(self):
        yield fuse.Direntry('_')
        for ns in self.kube.list_namespaces():
            yield fuse.Direntry(ns)


class NamespaceNode(Node):
    is_dir = True

    def readdir(self):
        pass


class ResourceGroupNode(Node):
    is_dir = True

    def readdir(self):
        pass


class ObjectNode(Node):
    is_dir = False
