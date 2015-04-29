from cinderclient.v1 import client as cinder_v1
from glanceclient import Client as glance_client
from keystoneclient.v2_0 import client as key_v2
from keystoneclient.openstack.common.apiclient import exceptions as keystone_exceptions
from neutronclient.v2_0 import client as neutron_v2
from novaclient.v1_1 import client as nova_v1
import swiftclient

from contextlib import contextmanager
from copy import deepcopy
import logging
import random
import string

log = logging.getLogger(__name__)

CINDER_ARGS = ['gigabytes', 'volumes']
NOVA_ARGS = ['ram', 'disk', 'vcpus', 'ephemeral', 'swap', 'instances']
GLANCE_ARGS = ['bytes', 'images']
SWIFT_ARGS = ['containers', 'bytes']

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
                                      auth_url=auth_url,
                                      endpoint_type='adminURL')
        self.neutron = neutron_v2.Client(username=username,
                                         password=password,
                                         tenant_name=tenant_name,
                                         auth_url=auth_url,
                                         endpoint_type='adminURL')
        token = self.keystone.auth_token
        image_url = self.keystone.service_catalog.url_for(service_type='image')
        self.glance = glance_client('1', token=token, endpoint=image_url)

    def __random_string(self, prefix='', length=10):
        chars = string.ascii_lowercase + string.digits
        s = ''.join(random.choice(chars) for _ in range(length))
        return prefix + s

    def __get_member_role(self):
        for role in self.keystone.roles.list():
            if role.name in ['_member_', 'member']:
                return role
        return None

    def __get_tenant(self, name):
        for tenant in self.keystone.tenants.list():
            if tenant.name == name:
                return tenant
        return None

    @contextmanager
    def temp_user(self, username, password):
        user = self.keystone.users.create(username, password, None)
        try:
            yield user
        finally:
            self.keystone.users.delete(user.id)

    def cinder_usage(self):
        log.debug('Loading cinder usage')
        # Generate default values for cinder args
        cinder_default = dict()
        for i in CINDER_ARGS:
            cinder_default[i] = 0
        # Cinder dict contains data for each tenant, and total
        cinder_dict = dict()
        cinder_dict['total'] = deepcopy(cinder_default)
        # For each volume, add to values based on size and tenant id
        for volume in self.cinder.volumes.list(search_opts={'all_tenants' : 1}):
            log.debug('Adding volume:%s to usage' % volume.id)
            # Set for tenant
            tenant_id = getattr(volume, 'os-vol-tenant-attr:tenant_id')
            cinder_dict.setdefault(tenant_id, deepcopy(cinder_default))
            cinder_dict[tenant_id]['gigabytes'] += volume.size
            cinder_dict[tenant_id]['volumes'] += 1
            # Set for totals
            cinder_dict['total']['gigabytes'] += volume.size
            cinder_dict['total']['volumes'] += 1
        return cinder_dict

    def __flavor_dict(self):
        # Flavor dict to call ram, vcpus and cores values
        log.debug('Loading flavor data')
        flavor_dict = dict()
        for flav in self.nova.flavors.list():
            log.debug('Adding flavor:%s' % flav.id)
            flavor_dict[flav.id] = dict()
            flavor_dict[flav.id]['ram'] = int(flav.ram)
            flavor_dict[flav.id]['disk'] = int(flav.disk)
            flavor_dict[flav.id]['vcpus'] = int(flav.vcpus)
            flavor_dict[flav.id]['ephemeral'] = getattr(flav, 'OS-FLV-EXT-DATA:ephemeral')
            try:
                flavor_dict[flav.id]['swap'] = int(flav.swap)
            except ValueError:
                flavor_dict[flav.id]['swap'] = 0
        return flavor_dict

    def nova_usage(self):
        log.debug('Loading nova data')
        # Make sure you can get flavors first
        flavors = self.__flavor_dict()
        # Set nova default dict
        nova_default = dict()
        for i in NOVA_ARGS:
            nova_default[i] = 0
        # Set up nova usage dict and totals
        nova_dict = dict()
        nova_dict['total'] = deepcopy(nova_default)
        for server in self.nova.servers.list(search_opts={'all_tenants' : 1}):
            log.debug('Adding server:%s to usage' % server.id)
            #args = vars(server)
            tenant_id = server.tenant_id
            try:
                flav = flavors[server.flavor['id']]
            except KeyError:
                log.error('Cannot find flavor:%s for server:%s' % (server.flavor['id'],
                                                                   server.id))
                continue
            nova_dict.setdefault(tenant_id, deepcopy(nova_default))
            # For every value in flavors
            for key, value in flav.iteritems():
                nova_dict[tenant_id][key] += value
                nova_dict['total'][key] += value
            # Also iterate instances
            nova_dict[tenant_id]['instances'] += 1
            nova_dict['total']['instances'] += 1
        return nova_dict

    def keystone_usage(self):
        log.debug('Loading keystone data')
        keystone_dict = dict()
        keystone_dict['total'] = dict()
        try:
            keystone_dict['total']['users'] = len(self.keystone.users.list())
            keystone_dict['total']['projects'] = len(self.keystone.tenants.list())
        except keystone_exceptions.Forbidden:
            log.error('Not authorized to get keystone information')
            keystone_dict['total']['users'] = 'not allowed'
            keystone_dict['total']['projects'] = 'not allowed'
        return keystone_dict

    def glance_usage(self):
        log.debug('Loading glance data')
        # Build default dict
        image_default = dict()
        for i in GLANCE_ARGS:
            image_default[i] = 0
        # Build image dict and totals
        image_dict = dict()
        image_dict['total'] = deepcopy(image_default)
        # For all private images
        # Keep list of images seen to double check for overlap
        images_seen = []
        for image in self.glance.images.list(is_public=False):
            log.debug('Adding image:%s to usage' % image.id)
            tenant_id = image.owner
            image_dict.setdefault(tenant_id, deepcopy(image_default))
            image_dict[tenant_id]['bytes'] += image.size
            image_dict[tenant_id]['images'] += 1
            image_dict['total']['bytes'] += image.size
            image_dict['total']['images'] += 1
            images_seen.append(image.id)
        # For all public images
        for image in self.glance.images.list(is_public=True):
            if image.id in images_seen:
                continue
            log.debug('Adding image:%s to usage' % image.id)
            tenant_id = image.owner
            image_dict.setdefault(tenant_id, deepcopy(image_default))
            image_dict[tenant_id]['bytes'] += image.size
            image_dict[tenant_id]['images'] += 1
            image_dict['total']['bytes'] += image.size
            image_dict['total']['images'] += 1
        return image_dict

    def swift_usage(self):
        log.debug('Loading swift data')
        # Build swift detault
        swift_default = dict()
        for i in SWIFT_ARGS:
            swift_default[i] = 0
        # Build with swift data
        swift_dict = dict()
        swift_dict['total'] = deepcopy(swift_default)
        # Swift is dumb and doesnt let admins query tenants directly
        # To get around this, create temporary user to delete afterwards
        member = self.__get_member_role()
        username = self.__random_string(prefix='user-')
        password = self.__random_string()
        with self.temp_user(username, password) as user:
            for tenant in self.keystone.tenants.list():
                log.debug('Gathering data for tenant:%s' % tenant.id)
                tenant.add_user(user.id, member.id)
                swift = swiftclient.client.Connection(auth_version='2',
                                                      user=username,
                                                      key=password,
                                                      tenant_name=tenant.name,
                                                      authurl=self.os_auth_url)
                info = swift.head_account()
                # Add values from information
                containers = int(info['x-account-container-count'])
                bytes_used = int(info['x-account-bytes-used'])
                if containers == 0 and bytes_used == 0:
                    continue
                swift_dict.setdefault(tenant.id, deepcopy(swift_default))
                swift_dict[tenant.id]['containers'] += containers
                swift_dict[tenant.id]['bytes'] += bytes_used
                swift_dict['total']['containers'] += containers
                swift_dict['total']['bytes'] += bytes_used
        return swift_dict

    def neutron_usage(self):
        log.debug('Loading neutron usage')
        usage = dict()
        default = {'networks' : 0, 'shared_networks' : 0}
        usage['total'] = deepcopy(default)
        try:
            networks = self.neutron.list_networks()['networks']
        except keystone_exceptions.EndpointNotFound:
            log.error('No neutron endpoint found')
            usage['total']['Endpoint'] = 'URL not found'
            return usage
        for net in networks:
            log.debug('Adding network:%s to usage' % net)
            tenant = self.__get_tenant(net['tenant_id'])
            usage.setdefault(tenant.id, deepcopy(default))
            usage[tenant.id]['networks'] += 1
            usage['total']['networks'] += 1
            if net['shared']:
                usage[tenant.id]['shared_networks'] += 1
                usage['total']['shared_networks'] += 1
        return usage

    def cloud_usage(self):
        usage = dict()
        usage['keystone'] = self.keystone_usage()
        usage['cinder'] = self.cinder_usage()
        usage['nova'] = self.nova_usage()
        usage['glance'] = self.glance_usage()
        usage['swift'] = self.swift_usage()
        usage['neutron'] = self.neutron_usage()
        return usage
