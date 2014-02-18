import argparse
from cinderclient.v1 import client as cinder_v1
from glanceclient import Client as glance_client
from keystoneclient.v2_0 import client as key_v2
import math
import time

DEFAULT_TIMEOUT = 3600
DEFAULT_INTERVAL = 5

class ImageConvert(object):
    def __init__(self, username, password, tenant_name, auth_url):
        self.keystone = key_v2.Client(username=username,
                                      password=password,
                                      tenant_name=tenant_name,
                                      auth_url=auth_url)
        token, image_endpoint = self.__setup_glance()
        self.glance = glance_client('1', endpoint=image_endpoint, token=token)

        self.cinder = cinder_v1.Client(username,
                                       password,
                                       tenant_name,
                                       auth_url)

    def __setup_glance(self):
        token = self.keystone.auth_token
        service_catalog = self.keystone.service_catalog
        catalog = service_catalog.catalog['serviceCatalog']
        glance_ip = None
        for endpoint in catalog:
            if 'image' == endpoint['type']:
                glance_ip = endpoint['endpoints'][0]['publicURL']
        return token, glance_ip

    def wait_for_condition(self, fn, f_args, whitelist=None, blacklist=None, TIMEOUT=DEFAULT_TIMEOUT):
        start = time.time()
        obj = fn(f_args)
        while obj.status not in whitelist:
            if obj.status in blacklist:
                return None
            if time.time() - start >= TIMEOUT:
                return None
            time.sleep(DEFAULT_INTERVAL)
            obj = fn(f_args)
        return obj.id

    def image_list(self):
        relevant_images = []
        all_images = self.glance.images.list()
        for i in all_images:
            if i.status == 'active' and i.disk_format == 'raw':
                relevant_images.append(i)
        return relevant_images

    def convert_image(self, image, delete=False):
        print 'Converting image:', image.id
        size_gb = math.ceil(image.size / ( 1024 * 1024 * 1024.0))
        print '--creating volume'
        volume = self.cinder.volumes.create(size_gb, imageRef=image.id)
        result = self.wait_for_condition(self.cinder.volumes.get, volume.id, ['available'], ['error'])
        if result is None:
            print 'error creating volume, exiting'
            return
        print '--volume:%s created' % volume.id

        print '--creating new image'
        new_image = self.cinder.volumes.upload_to_image(volume.id, True,  image.name + '-updated', 'bare', 'qcow2')
        image_id = new_image[1]['os-volume_upload_image']['image_id']
        result = self.wait_for_condition(self.glance.images.get, image_id, ['active'], ['error'])
        if result is None:
            print 'error creating image, exiting'
            return
        print '--image:%s created' % image_id

        print '--deleting created volume'
        self.wait_for_condition(self.cinder.volumes.get, volume.id, ['available'], ['error'])
        self.cinder.volumes.delete(volume.id)
        
        print '--updating new image'
        old_image_args = vars(image)['_info']
        image_args = dict()
        image_args['name'] = old_image_args.pop('name', None)
        image_args['is_public'] = old_image_args.pop('is_public', None) 
        self.glance.images.update(image_id, **image_args)

        print '--deleting original image'
        if delete:
            self.glance.images.delete(image)
        
        new_size = self.glance.images.get(image_id).size / ( 1024 * 1024 * 1024.0)
        return size_gb - new_size

    def shrink_image(self, image_id, delete=False):
        image = self.glance.images.get(image_id)
        saved = self.convert_image(image, delete=delete)
        print 'Program has freed up %s GB' % str(saved)

    def shrink_all_images(self, delete=False):
        total_saved = 0
        for image in self.image_list():
            total_saved += self.convert_image(image, delete=delete)
        print 'Program has freed up %s GB' % str(total_saved)

def parse_args():
    a = argparse.ArgumentParser(description='Shrink all raw images on a cluster')
    a.add_argument('username', help='Auth username')
    a.add_argument('password', help='Auth password')
    a.add_argument('tenant_name', help='Auth tenant name')
    a.add_argument('auth_url', help='Auth url')
    a.add_argument('image_id', help='Id of image to convert, "all" to convert all possible raw images')
    a.add_argument('--delete', action='store_true', help='Delete old images')
    return a.parse_args()
def main():
    args = vars(parse_args())
    i = ImageConvert(args['username'], args['password'], args['tenant_name'], args['auth_url'])
    if args['image_id'] == 'all':
        i.shrink_all_images(delete=args['delete'])
    else:
        i.shrink_image(args['image_id'], delete=args['delete'])
if __name__ == '__main__':
    main()
