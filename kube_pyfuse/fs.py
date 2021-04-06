import os
import stat
import errno
import itertools

import fuse

from . import node

fuse.fuse_python_api = (0, 2)

# TODO: add typing + flake checks


class FSError(OSError):
    def __init__(self, errno):
        super().__init__(errno, os.strerror(errno))
        self.errno = errno


class KubeFS(fuse.Fuse):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.root_node = node.RootNode()
        self.file_class = create_kube_file_class(self)
        self.truncated_files = {}

    def _path2node(self, path):
        path = path[1:]  # remove leading slash
        path_parts = path.split('/')
        if len(path_parts) == 1 and path_parts[0] == '':
            path_parts = []

        n = self.root_node
        for path_part in path_parts:
            if not n.is_dir:
                raise FSError(errno.EACCES)
            children = {child.name: child for child in n.get_children()}
            try:
                n = children[path_part]
            except KeyError as err:
                raise FSError(errno.ENOENT) from err

        return n

    def readdir(self, path, offset):
        n = self._path2node(path)

        if not n.is_dir:
            return -errno.EACCES

        return itertools.chain(
            (fuse.Direntry('.'), fuse.Direntry('..')),
            (fuse.Direntry(child.name) for child in n.get_children()),
        )

    def getattr(self, path):
        n = self._path2node(path)

        st = fuse.Stat()
        if n.is_dir:
            st.st_mode = stat.S_IFDIR | 0o777
            st.st_nlink = 2
        else:
            st.st_mode = stat.S_IFREG | 0o666
            st.st_nlink = 1

        nstat = n.get_stat()
        for k, v in nstat.items():
            setattr(st, k, v)

        try:
            size = self.truncated_files[path]
        except KeyError:
            pass
        else:
            st.st_size = size

        return st


def create_kube_file_class(_kubefs):
    class KubeFile:
        kubefs = _kubefs

        def __init__(self, path, flags, *args):
            print(hex(id(self)), 'init', path, oct(flags))
            self.path = path
            self.node = self.kubefs._path2node(path)

            self.is_dirty = False
            self.buf = None

            if flags & os.O_TRUNC:
                self.ftruncate(0)

        def _ensure_buf(self):
            if self.buf is not None:
                return

            self.buf = self.node.read()
            try:
                len = self.kubefs.truncated_files[self.path]
            except KeyError:
                pass
            else:
                self.buf = self.buf[:len]

        def read(self, size, offset):
            print(hex(id(self)), 'read', size, offset)
            self._ensure_buf()
            return self.buf[offset:offset+size]

        def write(self, buf, offset):
            print(hex(id(self)), 'write', len(buf), offset)
            print(repr(buf))
            self._ensure_buf()
            self.is_dirty = True
            self.buf = self.buf[:offset] + buf + self.buf[offset+len(buf):]
            self.kubefs.truncated_files.pop(self.path, None)
            return len(buf)

        def release(self, flags):
            print(hex(id(self)), 'release')
            # TODO: flush

        def flush(self):
            print(hex(id(self)), 'flush')
            if not self.is_dirty:
                return
            # TODO: write
            self.is_dirty = False

        def fsync(self, isfsyncfile):
            print(hex(id(self)), 'fsync')
            # TODO: flush

        def fgetattr(self):
            print(hex(id(self)), 'getattr')
            return self.kubefs.getattr(self.path)

        def ftruncate(self, size):
            print(hex(id(self)), 'ftruncate', size)
            self.kubefs.truncated_files[self.path] = size
            if self.buf is not None:
                self.buf = self.buf[:size]

    return KubeFile
