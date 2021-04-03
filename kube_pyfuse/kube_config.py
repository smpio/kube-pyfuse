import os

import kubernetes


def init():
    if os.getenv('KUBE_API_PROXY'):
        configuration = kubernetes.client.Configuration()
        configuration.host = os.getenv('KUBE_API_PROXY')
        kubernetes.client.Configuration.set_default(configuration)
    elif os.getenv('KUBE_IN_CLUSTER'):
        kubernetes.config.load_incluster_config()
    else:
        kubernetes.config.load_kube_config()
