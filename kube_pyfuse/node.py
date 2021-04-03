import fuse

import os
import stat
import errno


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
