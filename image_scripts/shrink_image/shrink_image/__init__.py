from contextlib import contextmanager
from cinderclient.v1 import client as cinder_v1
from glanceclient import Client as glance_client
from keystoneclient.v2_0 import client as key_v2
import logging
import math
import random
import string
import time

log = logging.getLogger(__name__)

class ShrinkImage(object):
    def __init__(self, username, password, tenant_name, auth_url):
        self.keystone = key_v2.Client(username=username,
                                      password=password,
                                      tenant_name=tenant_name,
                                      auth_url=auth_url)
        image_url = self.keystone.service_catalog.url_for(service_type='image')
        self.glance = glance_client('1', endpoint=image_url,
                                    token=self.keystone.auth_token)
        self.cinder = cinder_v1.Client(username, password,
                                       tenant_name, auth_url)

    def __random_string(self, prefix='', length=10):
        chars = string.ascii_lowercase + string.digits
        s = ''.join(random.choice(chars) for _ in range(length))
        return prefix + s

    def __wait_for(self, obj_id, function, whitelist, blacklist=[],
                   interval=5, timeout=3600):
        timeout = time.time() + timeout
        obj = function(obj_id)
        while obj.status not in whitelist:
            if time.time() >= timeout:
                return None
            if obj.status in blacklist:
                return None
            time.sleep(interval)
            obj = function(obj_id)
        return obj.id

    @contextmanager
    def __temp_volume(self, image_id):
        log.debug('Creating volume from image:%s' % image_id)
        image = self.glance.images.get(image_id)
        size = math.ceil(image.size / (1024*1024*1024.0))
        vol = self.cinder.volumes.create(size, imageRef=image_id)
        log.debug('Volume created:%s' % vol.id)
        result = self.__wait_for(vol.id, self.cinder.volumes.get,
                                 ['available'], blacklist=['error'])
        try:
            yield result
        finally:
            self.__wait_for(vol.id, self.cinder.volumes.get,
                            ['available'], blacklist=['error'])
            self.cinder.volumes.delete(vol.id)

    def shrink_image(self, image_id, image_name=None):
        log.debug('Converting image:%s' % image_id)
        result = None
        image = self.glance.images.get(image_id)
        min_size = int(math.ceil(image.size / (1024*1024*1024.0)))
        if image.disk_format == 'qcow2':
            log.error('Cannot shrink image, is already qcow2')
            return
        with self.__temp_volume(image_id) as volume:
            if not volume:
                log.error('Error creating volume')
                return
            if not image_name:
                image_name = self.__random_string(prefix='image-')
            log.debug('Creating image from volume:%s' % volume)
            image_info = self.cinder.volumes.upload_to_image(volume,
                                                             True,
                                                             image_name,
                                                             'bare',
                                                             'qcow2')
            image_id = image_info[1]['os-volume_upload_image']['image_id']
            log.debug('Image created:%s' % image_id)
            result = self.__wait_for(image_id, self.glance.images.get,
                                     ['active'], blacklist=['error'])
            log.debug('Min size updated:%s' % min_size)
            self.glance.images.update(image_id, min_disk=min_size)
        return result

    def shrink_all_images(self):
        images_converted = set([])
        for image in self.glance.images.list(is_public=False):
            if not image.id in images_converted:
                new_image = self.shrink_image(image.id, image_name=image.name + '-converted')
                if new_image:
                    images_converted.add(new_image)
            images_converted.add(image.id)
        for image in self.glance.images.list(is_public=True):
            if not image.id in images_converted:
                new_image = self.shrink_image(image.id, image_name=image.name + '-converted')
                if new_image:
                    images_converted.add(new_image)
            images_converted.add(image.id)
