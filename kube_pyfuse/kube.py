import sys
from collections import defaultdict

import kubernetes

from . import kube_config


class Kube:
    def __init__(self):
        kube_config.init()
        self.v1 = kubernetes.client.CoreV1Api()
        self.client = kubernetes.client.ApiClient()

        dynamic_client = kubernetes.dynamic.DynamicClient(client=self.client)
        self.discoverer = kubernetes.dynamic.EagerDiscoverer(
            client=dynamic_client,
            cache_file=None,
        )
        self._load_resource_groups()

    def _load_resource_groups(self):
        api_groups = self.discoverer.parse_api_groups()
        self.namespaced_resources = defaultdict(dict)
        self.global_resources = defaultdict(dict)
        for api_group in api_groups.values():
            for resource_group_name, resource_group_versions in api_group.items():
                for resource_group_version, resource_group in resource_group_versions.items():
                    if not resource_group.preferred:
                        continue
                    for kind, resource_list in resource_group.resources.items():
                        if not resource_list:
                            print('No resources for', resource_group_name, resource_group_version, kind,
                                  file=sys.stderr)
                            continue
                        resource = resource_list[0]
                        if getattr(resource, 'base_kind', None):
                            continue  # skip *List resources
                        verbs = getattr(resource, 'verbs', None) or []
                        if 'get' in verbs and 'list' in verbs:
                            if resource.namespaced:
                                self.namespaced_resources[resource_group_name][kind] = resource
                            else:
                                self.global_resources[resource_group_name][kind] = resource

    def get_resource_url(self, resource, namespace, object_name):
        if resource.group == '':
            url = '/api'
        else:
            url = '/apis/' + resource.group
        url += '/' + resource.api_version
        if resource.namespaced:
            url += '/namespaces/' + namespace
        url += '/' + resource.name
        if object_name:
            url += '/' + object_name
        return url

    def get_resource(self, resource, namespace, object_name=None, content_type='application/json'):
        url = self.get_resource_url(resource, namespace, object_name)
        ret = self.client.call_api(url, 'GET', header_params={
            'Accept': content_type
        }, auth_settings=['BearerToken'], response_type=object)
        return ret[0]


kube = Kube()
