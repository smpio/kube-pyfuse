import os
import stat
import errno
import itertools

import fuse

from . import node

fuse.fuse_python_api = (0, 2)

# TODO: add typing + flake checks


class Error(Exception):
    def __init__(self, my_errno):
        super().__init__(my_errno)
        self.my_errno = my_errno


class KubeFS(fuse.Fuse):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.root_node = node.RootNode()

    def _path2node(self, path):
        path = path[1:]  # remove leading slash
        path_parts = path.split('/')
        if len(path_parts) == 1 and path_parts[0] == '':
            path_parts = []

        n = self.root_node
        for path_part in path_parts:
            if not n.is_dir:
                raise Error(errno.EACCES)
            children = {child.name: child for child in n.get_children()}
            try:
                n = children[path_part]
            except KeyError as err:
                raise Error(errno.ENOENT) from err

        return n

    def readdir(self, path, offset):
        try:
            n = self._path2node(path)
        except Error as err:
            return -err.my_errno

        if not n.is_dir:
            return -errno.EACCES

        return itertools.chain(
            (fuse.Direntry('.'), fuse.Direntry('..')),
            (fuse.Direntry(child.name) for child in n.get_children()),
        )

    def getattr(self, path):
        try:
            n = self._path2node(path)
        except Error as err:
            return -err.my_errno

        st = fuse.Stat()
        if n.is_dir:
            st.st_mode = stat.S_IFDIR | 0o755
            st.st_nlink = 2
        else:
            st.st_mode = stat.S_IFREG | 0o444
            st.st_nlink = 1

        nstat = n.get_stat()
        for k, v in nstat.items():
            setattr(st, k, v)

        return st

    def open(self, path, flags):
        try:
            n = self._path2node(path)
        except Error as err:
            return -err.my_errno

        if n.is_dir:
            return -errno.EACCES

        accmode = os.O_RDONLY | os.O_WRONLY | os.O_RDWR
        if (flags & accmode) != os.O_RDONLY:
            return -errno.EACCES

    def read(self, path, size, offset):
        try:
            n = self._path2node(path)
        except Error as err:
            return -err.my_errno

        if n.is_dir:
            return -errno.EACCES

        data = n.read()
        return data[offset:offset+size]
