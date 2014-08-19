from cinderclient.v1 import client as cinder_v1
from contextlib import contextmanager
from copy import deepcopy
from glanceclient import Client as glance_client
import json
from keystoneclient.v2_0 import client as key_v2
import logging
from novaclient.v1_1 import client as nova_v1
import random
import string
import time

log = logging.getLogger(__name__)

class VolumeBoot(object):
    def __init__(self, username, password, tenant_name, auth_url):
        self.cinder = cinder_v1.Client(username, password,
                                       tenant_name, auth_url)
        self.nova = nova_v1.Client(username, password, tenant_name, auth_url)
        self.keystone = key_v2.Client(username=username,
                                      password=password,
                                      tenant_name=tenant_name,
                                      auth_url=auth_url)
        image_url = self.keystone.service_catalog.url_for(service_type='image')
        self.glance = glance_client('1', token=self.keystone.auth_token,
                                    endpoint=image_url)

    def __random_string(self, prefix='', length=10):
        chars = string.ascii_lowercase + string.digits
        s = ''.join(random.choice(chars) for _ in range(length))
        return prefix + s

    def __wait_for(self, obj_id, function, whitelist, blacklist=[],
                   interval=5, timeout=3600):
        expected_timeout = time.time() + timeout
        obj = function(obj_id)
        while obj.status not in whitelist:
            if obj.status in blacklist:
                return None
            if time.time() >= expected_timeout:
                return None
            time.sleep(interval)
            obj = function(obj_id)
        return obj.id

    def __wait_for_delete(self, obj_id, list_function, interval=5,
                          timeout=3600):
        expected_timeout = time.time() + timeout
        obj_list = list_function()
        while time.time() >= expected_timeout:
            found = False
            for obj in obj_list:
                if obj.id == obj_id:
                    found = True
                    break
            if found:
                return True
        return False

    @contextmanager
    def __temp_image(self, flavor, image, key_name):
        log.debug('Creating temp image for key injection')
        server_name = self.__random_string(prefix='server-')
        server = self.nova.servers.create(server_name, image, flavor,
                                          key_name=key_name)
        log.debug('Created server:%s' % server.id)
        result = self.__wait_for(server.id, self.nova.servers.get,
                                 ['ACTIVE'], blacklist=['ERROR'])
        if result:
            log.debug('Powering down temp server for snapshot')
            self.nova.servers.stop(server.id)
            result = self.__wait_for(server.id, self.nova.servers.get,
                                     ['SHUTOFF'], blacklist=['ERROR'])
        if not result:
            log.error('Error creating instance')
            try:
                yield None
                return
            finally:
                log.debug('Cleaning up server:%s' % server.id)
                self.nova.servers.delete(server.id)

        log.debug('Creating snapshot')
        image_name = self.__random_string(prefix='image-')
        image_id = self.nova.servers.create_image(server.id, image_name)
        log.debug('Snapshot created:%s' % image_id)
        image = self.__wait_for(image_id, self.nova.images.get,
                                ['ACTIVE'], blacklist=['ERROR'])
        try:
            yield image
        finally:
            log.debug('Cleaning up server:%s' % server.id)
            self.nova.servers.delete(server.id)
            log.debug('Cleaning up image:%s' % image)
            self.nova.images.delete(image)

    def __create_bootable_volume(self, size, image_id, volume_type):
        log.debug('Creating bootable volume')
        vol = self.cinder.volumes.create(size,
                                         imageRef=image_id,
                                         volume_type=volume_type)
        log.debug('Volume created:%s' % vol.id)
        result = self.__wait_for(vol.id, self.cinder.volumes.get,
                                 ['available'], blacklist=['error'])
        return result

    def __create_instance(self, flavor, image, name, volume, key_name,
                          networks, security_groups):
        mapping = {'vda' : '%s:::1' % volume}
        if networks:
            networks = [{'net-id' : i} for i in networks]
        log.debug('Creating instance')
        server = self.nova.servers.create(name, image, flavor,
                                          block_device_mapping=mapping,
                                          nics=networks,
                                          security_groups=security_groups,
                                          key_name=key_name)
        log.debug('Creating instance:%s' % server.id)
        result = self.__wait_for(server.id, self.nova.servers.get,
                                 ['ACTIVE'], blacklist=['ERROR'])
        return result

    def boot_from_volume(self, flavor, image, name, size, temp_flavor,
                         key_name=None, volume_type=None, networks=None,
                         security_groups=None, no_temp=False):
        if key_name and no_temp == False:
            log.debug('Creating temporary instance for key injection')
            with self.__temp_image(temp_flavor, image, key_name) as injected_image:
                if not injected_image:
                    log.error('Error creating key injected image, exiting')
                    return None
                volume = self.__create_bootable_volume(size, injected_image, volume_type)
        else:
            volume = self.__create_bootable_volume(size, image, volume_type)
        return self.__create_instance(flavor, image, name, volume, key_name,
                                      networks, security_groups)

    @contextmanager
    def __temp_volume(self, instance_id):
        image_name = self.__random_string(prefix='image-')
        log.debug('Creating instance snapshot')
        snapshot_id = self.nova.servers.create_image(instance_id, image_name)
        log.debug('Created snapshot:%s' % snapshot_id)
        image = self.glance.images.get(snapshot_id)
        mappings = json.loads(image.properties['block_device_mapping'])
        all_snaps = []
        for mappin in mappings:
            all_snaps.append(mappin['snapshot_id'])
            try:
                if mappin['device_name'] == 'vda':
                    snapshot = self.cinder.volume_snapshots.get(mappin['snapshot_id'])
                    log.debug('Found volume snapshot:%s' % mappin['snapshot_id'])
                    self.__wait_for(mappin['snapshot_id'],
                                    self.cinder.volume_snapshots.get,
                                    ['available'],
                                    blacklist=['error'])
            except KeyError:
                # Pre icehouse versions have different mappings
                _snapshot = self.cinder.volume_snapshots.get(mappin['snapshot_id'])
                _vol = self.cinder.volumes.get(_snapshot.volume_id)
                for attach in _vol.attachments:
                    if attach['device'] == 'vda' and instance_id == attach['server_id']:
                        snapshot = self.cinder.volume_snapshots.get(mappin['snapshot_id'])
                        log.debug('Found volume snapshot:%s' % snapshot.id)
                        self.__wait_for(snapshot.id,
                                        self.cinder.volume_snapshots.get,
                                        ['available'],
                                        blacklist=['error'])
                        break
        log.debug('Creating volume from snapshot')
        vol = self.cinder.volumes.create(snapshot.size, snapshot_id=snapshot.id)
        log.debug('Created volume:%s' % vol.id)
        self.__wait_for(vol.id, self.cinder.volumes.get,
                        ['available'], blacklist=['error'])
        try:
            yield vol
        finally:
            log.debug('Deleting instance snapshot:%s' % snapshot_id)
            self.glance.images.delete(snapshot_id)
            log.debug('Deleting created volume:%s' % vol.id)
            self.cinder.volumes.delete(vol.id)
            self.__wait_for_delete(vol.id, self.cinder.volumes.list)
            log.debug('Deleting volume snapshots:%s' % all_snaps)
            for snap in all_snaps:
                self.cinder.volume_snapshots.delete(snap)

    def snapshot_instance(self, instance_id, image_name=None):
        with self.__temp_volume(instance_id) as volume:
            if not image_name:
                image_name = self.__random_string(prefix='image-')
            log.debug('Creating image from volume:%s' % volume.id)
            image_info = self.cinder.volumes.upload_to_image(volume.id,
                                                             True,
                                                             image_name,
                                                             'bare',
                                                             'qcow2')
            image_id = image_info[1]['os-volume_upload_image']['image_id']
            log.debug('Created image:%s' % image_id)
            self.__wait_for(image_id, self.glance.images.get,
                            ['active'], blacklist=['error'])
