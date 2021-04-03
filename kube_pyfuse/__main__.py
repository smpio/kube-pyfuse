import fuse

from .fs import HelloFS

fuse.fuse_python_api = (0, 2)


# TODO: add signal handlers (SIGTERM, SIGINT)
def main():
    server = HelloFS(version="%prog " + fuse.__version__, dash_s_do='setsingle')
    server.parse(errex=1)
    server.main()


if __name__ == '__main__':
    main()
