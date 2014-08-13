from cinderclient.v1 import client as cinder_v1
from contextlib import contextmanager
from copy import deepcopy
from glanceclient import Client as glance_client
from keystoneclient.v2_0 import client as key_v2
from novaclient.v1_1 import client as nova_v1
import random
import string
import swiftclient

class CloudUsage(object):
    def __init__(self, username, password, tenant_name, auth_url):
        self.os_auth_url = auth_url

        self.cinder = cinder_v1.Client(username, password,
                                       tenant_name, auth_url)
        self.nova = nova_v1.Client(username, password,
                                   tenant_name, auth_url)
        self.keystone = key_v2.Client(username=username,
                                      password=password,
                                      tenant_name=tenant_name,
                                      auth_url=auth_url)
        token = self.keystone.auth_token
        image_url = self.keystone.service_catalog.url_for(service_type='image')
        self.glance = glance_client('1', token=token, endpoint=image_url)

    def __random_string(self, prefix='', length=10):
        chars = string.ascii_lowercase + string.digits
        s = ''.join(random.choice(chars) for _ in range(length))
        return prefix + s

    def __get_member_role(self):
        for role in self.keystone.roles.list():
            if '_member_' == role.name:
                return role
        return None

    @contextmanager
    def temp_user(self, username, password):
        user = self.keystone.users.create(username, password, None)
        try:
            yield user
        finally:
            self.keystone.users.delete(user.id)

    def cinder_usage(self):
        volume_dict = dict()
        volume_default = {'gigabytes' : 0, 'volumes' : 0}
        volume_dict['total'] = deepcopy(volume_default)
        for volume in self.cinder.volumes.list(search_opts={'all_tenants' : 1}):
            vol = vars(volume)
            tenant_id = vol['os-vol-tenant-attr:tenant_id']
            volume_dict.setdefault(tenant_id, deepcopy(volume_default))
            volume_dict[tenant_id]['gigabytes'] += vol['size']
            volume_dict[tenant_id]['volumes'] += 1

            volume_dict['total']['gigabytes'] += vol['size']
            volume_dict['total']['volumes'] += 1
        return volume_dict

    def __flavor_dict(self):
        flavor_dict = dict()
        for flav in self.nova.flavors.list():
            args = vars(flav)
            id = args.pop('id')
            flavor_dict[id] = dict()
            flavor_dict[id]['ram'] = int(args['ram'])
            flavor_dict[id]['disk'] = int(args['disk'])
            flavor_dict[id]['vcpus'] = int(args['vcpus'])
            flavor_dict[id]['ephemeral'] = int(args['OS-FLV-EXT-DATA:ephemeral'])
            try:
                flavor_dict[id]['swap'] = int(args['swap'])
            except ValueError:
                flavor_dict[id]['swap'] = 0
        return flavor_dict

    def nova_usage(self):
        flavors = self.__flavor_dict()
        nova_dict = dict()
        nova_default = {'ram' : 0, 'disk' : 0, 'vcpus' : 0,
                        'ephemeral' : 0, 'swap' : 0, 'instances' : 0,
                       }
        nova_dict['total'] = deepcopy(nova_default)
        for server in self.nova.servers.list(search_opts={'all_tenants' : 1}):
            args = vars(server)
            tenant_id = args['tenant_id']
            flav = flavors[args['flavor']['id']]
            nova_dict.setdefault(tenant_id, deepcopy(nova_default))
            for key, value in flav.iteritems():
                nova_dict[tenant_id][key] += value
                nova_dict['total'][key] += value
            nova_dict[tenant_id]['instances'] += 1
            nova_dict['total']['instances'] += 1
        return nova_dict

    def keystone_usage(self):
        keystone_dict = dict()
        keystone_dict['total'] = dict()
        keystone_dict['total']['users'] = len(self.keystone.users.list())
        keystone_dict['total']['projects'] = len(self.keystone.tenants.list())
        return keystone_dict

    def glance_usage(self):
        image_dict = dict()
        image_default = {'bytes' : 0, 'images' : 0}
        image_dict['total'] = deepcopy(image_default)
        for image in self.glance.images.list(is_public=False):
            args = vars(image)
            image_dict.setdefault(args['owner'], deepcopy(image_default))
            image_dict[args['owner']]['bytes'] += args['size']
            image_dict[args['owner']]['images'] += 1
            image_dict['total']['bytes'] += args['size']
            image_dict['total']['images'] += 1
        for image in self.glance.images.list(is_public=True):
            args = vars(image)
            image_dict.setdefault(args['owner'], deepcopy(image_default))
            image_dict[args['owner']]['bytes'] += args['size']
            image_dict[args['owner']]['images'] += 1
            image_dict['total']['bytes'] += args['size']
            image_dict['total']['images'] += 1
        return image_dict

    def swift_usage(self):
        swift_dict = dict()
        swift_default = {'containers' : 0, 'bytes' : 0}
        swift_dict['total'] = deepcopy(swift_default)
        member = self.__get_member_role()
        username = self.__random_string(prefix='user-')
        password = self.__random_string()
        with self.temp_user(username, password) as user:
            for tenant in self.keystone.tenants.list():
                tenant.add_user(user.id, member.id)
                swift = swiftclient.client.Connection(auth_version='2',
                                                      user=username,
                                                      key=password,
                                                      tenant_name=tenant.name,
                                                      authurl=self.os_auth_url)
                info = swift.head_account()
                swift_dict.setdefault(tenant.id, deepcopy(swift_default))
                swift_dict[tenant.id]['containers'] +=  int(info['x-account-container-count'])
                swift_dict[tenant.id]['bytes'] += int(info['x-account-bytes-used'])
                swift_dict['total']['containers'] +=  int(info['x-account-container-count'])
                swift_dict['total']['bytes'] += int(info['x-account-bytes-used'])
        return swift_dict

    def cloud_usage(self):
        usage = dict()
        usage['cinder'] = self.cinder_usage()
        usage['nova'] = self.nova_usage()
        usage['keystone'] = self.keystone_usage()
        usage['glance'] = self.glance_usage()
        usage['swift'] = self.swift_usage()
        return usage
