import os
import sys
import stat
import errno
import itertools

import fuse
import kubernetes

from . import node
from utils.collections import AutocleaningDefaultdict

fuse.fuse_python_api = (0, 2)

# TODO: add typing + flake checks


class KubeFS(fuse.Fuse):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.root_node = node.RootNode()
        self.file_class = create_kube_file_class(self)
        self._buffers = {}
        self._open_counters = AutocleaningDefaultdict(int)

    def lowwrap(self, fname):
        fun = super().lowwrap(fname)

        def wrapper(*args, **kwargs):
            try:
                return fun(*args, **kwargs)
            except kubernetes.client.exceptions.ApiException as err:
                print('Kubernetes error:', err, file=sys.stderr)
                if err.status == 400:
                    # invalid request
                    raise FSError(errno.EINVAL) from err
                if err.status == 404:
                    # invalid request
                    raise FSError(errno.ENOENT) from err
                elif err.status == 422:
                    # invalid manifest
                    raise FSError(errno.EINVAL) from err
                else:
                    # other errors
                    raise FSError(errno.EIO) from err

        return wrapper

    def _path2node(self, path):
        path = path[1:]  # remove leading slash
        path_parts = path.split('/')
        if len(path_parts) == 1 and path_parts[0] == '':
            path_parts = []

        n = self.root_node
        for path_part in path_parts:
            if not n.is_dir:
                raise FSError(errno.ENOTDIR)
            children = {child.name: child for child in n.get_children()}
            try:
                n = children[path_part]
            except KeyError as err:
                raise FSError(errno.ENOENT) from err

        return n

    def readdir(self, path, offset):
        n = self._path2node(path)

        if not n.is_dir:
            return -errno.ENOTDIR

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
            st.st_size = len(self._buffers[path])
        except KeyError:
            pass

        return st


def create_kube_file_class(_kubefs):
    class KubeFile:
        kubefs = _kubefs

        def __init__(self, path, flags, *args):
            debug(hex(id(self)), 'init', path, hex(flags), *args)

            self.path = path
            self.node = self.kubefs._path2node(path)

            self.is_dirty = False
            self.kubefs._open_counters[self.path] += 1

            if flags & os.O_TRUNC:
                self.ftruncate(0)

        @property
        def _buffer(self):
            try:
                data = self.kubefs._buffers[self.path]
            except KeyError:
                data = self.kubefs._buffers[self.path] = self.node.read()
            return data

        @_buffer.setter
        def _buffer(self, data):
            self.kubefs._buffers[self.path] = data
            self.is_dirty = True

        def read(self, size, offset):
            debug(hex(id(self)), 'read', size, offset)
            return self._buffer[offset:offset+size]

        def write(self, data, offset):
            debug(hex(id(self)), 'write', offset, repr(data))
            self._buffer = self._buffer[:offset] + data + self._buffer[offset+len(data):]
            return len(data)

        def release(self, flags):
            debug(hex(id(self)), 'release')
            self.is_dirty = False
            self.kubefs._open_counters[self.path] -= 1
            if self.kubefs._open_counters[self.path] == 0:
                self.kubefs._buffers.pop(self.path, None)

        def flush(self):
            debug(hex(id(self)), 'flush')
            if not self.is_dirty:
                return
            self.node.write(self._buffer)
            self.is_dirty = False

        def fgetattr(self):
            debug(hex(id(self)), 'getattr')
            return self.kubefs.getattr(self.path)

        def ftruncate(self, size):
            debug(hex(id(self)), 'ftruncate', size)
            if size == 0:
                self._buffer = b''
            else:
                self._buffer = self._buffer[:size]

    return KubeFile


class FSError(OSError):
    def __init__(self, errno):
        super().__init__(errno, os.strerror(errno))
        self.errno = errno


def debug(*args):
    print(*args, file=sys.stderr)
