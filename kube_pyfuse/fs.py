import itertools
from collections.abc import Iterable

import fuse

from . import node
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
            cls = node.RootNode
        elif len(path_parts) == 1:
            cls = node.NamespaceNode
        elif len(path_parts) == 2:
            cls = node.ResourceGroupNode
        elif len(path_parts) == 3:
            cls = node.KindNode
        elif len(path_parts) == 4:
            cls = node.ObjectNode
        else:
            cls = node.Node

        return cls(path_parts, self.kube)

    def readdir(self, path, offset):
        n = self._path2node(path)
        try:
            return itertools.chain((fuse.Direntry('.'), fuse.Direntry('..')), list(n.readdir()))
        except node.NodeError as err:
            return -err.my_errno

    def getattr(self, path):
        node = self._path2node(path)
        return node.getattr()

    def open(self, path, flags):
        node = self._path2node(path)
        return node.open(flags)

    def read(self, path, size, offset):
        node = self._path2node(path)
        return node.read(size, offset)
