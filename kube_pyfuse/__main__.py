import fuse

from .fs import KubeFS


# TODO: add signal handlers (SIGTERM, SIGINT)
def main():
    server = KubeFS(version="%prog " + fuse.__version__, dash_s_do='setsingle')
    server.parse(errex=1)
    server.main()


if __name__ == '__main__':
    main()
