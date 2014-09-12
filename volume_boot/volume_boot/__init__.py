import boto
from boto.s3 import connection as s3_connection
from boto.exception import S3ResponseError as s3_error
from cinderclient.v1 import client as cinder_v1
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from glanceclient import Client as glance_client
import json
from keystoneclient.v2_0 import client as key_v2
import logging
from novaclient.v1_1 import client as nova_v1
import os
import random
import string
import tempfile
import time
from urlparse import urlparse


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

        self.s3 = self.__s3_client()

    def __s3_client(self):
        creds = self.keystone.ec2.list(self.keystone.user_id)
        if len(creds) == 0:
            self.keystone.ec2.create(self.keystone.user_id,
                                     self.keystone.tenant_id)
            creds = self.keystone.ec2.list(self.keystone.user_id)
        cred = creds[-1]
        s3_url = urlparse(self.keystone.service_catalog.url_for(service_type='object-store'))
        host, port = s3_url.netloc.split(':')
        return boto.connect_s3(aws_access_key_id=cred.access,
                               aws_secret_access_key=cred.secret,
                               host=host,
                               port=int(port),
                               is_secure=False,
                               calling_format=s3_connection.OrdinaryCallingFormat())

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
            time.sleep(interval)
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
            self.__wait_for(vol.id, self.cinder.volumes.get,
                            ['available'], blacklist=['error'])
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
        return image_id

    def __delete_old_backups(self, instance_id, max_backups):
        log.debug('Deleting old backups, %s allowed' % max_backups)
        backups = []
        for image in self.glance.images.list():
            try:
                if instance_id == image.properties['backup_instance_id']:
                    backups.append(image)
            except KeyError:
                continue
        num_backups = len(backups)
        log.debug('Found %s backups, %s are allowed' % (num_backups, max_backups))
        if num_backups > max_backups:
            log.debug('Deleting old backups:%s' % backups)
            delete_amount = num_backups - max_backups
            delete_backups = []
            for backup in backups:
                if len(delete_backups) < delete_amount:
                    delete_backups.append(backup)
                    continue
                delete_index = None
                for count, deleted in enumerate(delete_backups):
                    if deleted.properties['backup_timestamp'] > backup.properties['backup_timestamp']:
                        delete_index = count
                        break
                if delete_index:
                    delete_backups[delete_index] = backup
            for backup in delete_backups:
                log.debug('Deleting backup:%s' % backup.id)
                self.glance.images.delete(backup.id)

    def __convert_to_swift(self, image_id, bucket_name, key_name, metadata=None):
        log.debug('Converting image:%s to swift object' % image_id)
        with tempfile.NamedTemporaryFile() as f:
            log.debug('Writing image to file:%s' % f.name)
            with open(f.name, 'w+'):
                for chunk in self.glance.images.data(image_id, do_checksum=False):
                    f.write(chunk)
            log.debug('Getting bucket:%s' % bucket_name)
            try:
                bucket = self.s3.get_bucket(bucket_name)
                log.debug('Bucket exists')
            except s3_error:
                log.debug('Creating bucket:%s' % bucket_name)
                bucket = self.s3.create_bucket(bucket_name)
            log.debug('Getting key:%s' % key_name)
            if bucket.get_key(key_name):
                bucket.delete_key(key_name)
            key = bucket.new_key(key_name=key_name)
            log.debug('Have key:%s' % key_name)
            log.debug('Setting contents from file:%s' % f.name)
            with open(f.name, 'r') as f:
                key.set_contents_from_file(f)
            key.update_metadata(metadata)

    def __delete_old_swift(self, max_num, bucket_name):
        bucket = self.s3.get_bucket(bucket_name)
        keys = bucket.get_all_keys()
        num_backups = len(keys)
        log.debug('Found %s backups, %s are allowed' % (num_backups, max_num))
        if num_backups > max_num:
            log.debug('Deleting old backups:%s' % keys)
            delete_amount = num_backups - max_num
            delete_backups = []
            for backup in keys:
                if len(delete_backups) < delete_amount:
                    delete_backups.append(backup)
                    continue
                delete_index = None
                for count, deleted in enumerate(delete_backups):
                    if deleted.get_metadata('timestamp') > backup.get_metadata('timestamp'):
                        delete_index = count
                        break
                if delete_index:
                    delete_backups[delete_index] = backup
            for backup in delete_backups:
                log.debug('Deleting backup:%s' % backup)
                bucket.delete_key(backup.name)

    def backup_instance(self, instance_id, max_num, swift=True):
        # Check for number of backups
        instance_name = self.nova.servers.get(instance_id).name
        image_name = '%s-%s' % (instance_name, time.time())
        backup_image = self.snapshot_instance(instance_id, image_name=image_name)
        metadata = {'backup_instance_id' : instance_id, 'backup_timestamp' : time.time()}
        log.debug('Updating image metadata:%s' % metadata)
        self.glance.images.update(backup_image, properties=metadata)
        if swift:
            bucket_name = 'instance-%s-backups' % instance_id
            key_name = 'backup-%s' % datetime.utcnow()
            metadata = {'timestamp' : time.time()}
            self.__convert_to_swift(backup_image, bucket_name, key_name,
                                    metadata=metadata)
            self.glance.images.delete(backup_image)
            if max_num:
                self.__delete_old_swift(max_num, bucket_name)
        elif max_num:
            self.__delete_old_backups(instance_id, max_num)
