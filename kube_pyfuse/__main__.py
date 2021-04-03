import sys
import signal

import fuse

from .fs import KubeFS


def main():
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    server = KubeFS(version="%prog " + fuse.__version__, dash_s_do='setsingle')
    server.parse(errex=1)
    server.main()


def shutdown(signum, frame):
    sys.exit(0)


if __name__ == '__main__':
    main()
