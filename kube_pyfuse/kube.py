import kubernetes

from . import kube_config


class Kube:
    def __init__(self):
        kube_config.init()
        self.v1 = kubernetes.client.CoreV1Api()

    def list_namespaces(self):
        result = self.v1.list_namespace()
        for ns in result.items:
            yield ns.metadata.name
