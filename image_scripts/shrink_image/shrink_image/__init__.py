from contextlib import contextmanager
from cinderclient.v1 import client as cinder_v1
from glanceclient import Client as glance_client
from keystoneclient.v2_0 import client as key_v2
import math
import random
import string
import time

class ShrinkImage(object):
    def __init__(self, username, password, tenant_name, auth_url):
        self.keystone = key_v2.Client(username=username,
                                      password=password,
                                      tenant_name=tenant_name,
                                      auth_url=auth_url)
        image_url = self.keystone.service_catalog.url_for(service_type='type')
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
        image = self.glance.images.get(image_id)
        size = math.ceil(image.size / (1024*1024*1024.0))
        vol = self.cinder.volumes.create(size, imageRef=image_id)
        result = self.__wait_for(vol.id, self.cinder.volumes.get,
                                 ['available'], blacklist=['error'])
        try:
            yield result
        finally:
            self.cinder.volumes.delete(vol.id)

    def shrink_image(self, image_id, image_name=None):
        with self.__temp_volume(image_id) as volume:
            if not image_name:
                image_name = self.__random_string(prefix='image-')
            image_info = self.cinder.volumes.upload_to_image(volume.id,
                                                             True,
                                                             image_name,
                                                             'bare',
                                                             'qcow2')
        image_id = image_info[1]['os_image_upload']['image_id']
        result = self.__wait_for(image_id, self.glance.images.get,
                                 ['active'], blacklist=['error'])
        return result

    def shrink_all_images(self):
        for image in self.glance.images.list(is_public=True):
            self.shrink_image(image.id)
        for image in self.glance.images.list(is_public=False):
            self.shrink_image(image.id)
