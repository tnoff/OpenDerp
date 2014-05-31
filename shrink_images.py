import argparse
from cinderclient.v1 import client as cinder_v1
from glanceclient import Client as glance_client
from keystoneclient.v2_0 import client as key_v2
import logging
import math
import os
import time

DEFAULT_TIMEOUT = 3600
DEFAULT_INTERVAL = 5
GB = 1024 * 1024 * 1024.0

logging_format = '%(asctime)s--%(levelname)s--%(message)s'
logging.basicConfig(format=logging_format, level=logging.INFO)
log = logging.getLogger(__name__)

def setup_glance(args):
    keystone = key_v2.Client(username=args['username'],
                             password=args['password'],
                             tenant_name=args['tenant_name'],
                             auth_url=args['auth_url'])

    token = keystone.auth_token
    service_catalog = keystone.service_catalog
    catalog = service_catalog.catalog['serviceCatalog']
    glance_ip = None
    for endpoint in catalog:
        if 'image' == endpoint['type']:
            glance_ip = endpoint['endpoints'][0]['publicURL']
    glance = glance_client('1', endpoint=glance_ip, token=token)
    return glance

def wait_for_condition(fn, f_args, whitelist=None, blacklist=None,
                       TIMEOUT=DEFAULT_TIMEOUT):
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

def convert_image(args, image, delete=False):
    logging.info('Converting image:%s' % image.id)
    size_gb = math.ceil(image.size / (GB))
    old_size = image.size
    logging.info('Creating volume from image')
    cinder = cinder_v1.Client(args['username'],
                              args['password'],
                              args['tenant_name'],
                              args['auth_url'])
    glance = setup_glance(args)
    volume = cinder.volumes.create(size_gb, imageRef=image.id)
    logging.info('Volume:%s created, waiting' % volume.id)
    result = wait_for_condition(cinder.volumes.get, volume.id,
                                ['available'], ['error'])
    if result is None:
        log.error('Error creating volume:%s, exiting' % volume.id)
        return
    logging.info('Creating new image')
    image_name = image.name + '-updated'
    new_image = cinder.volumes.upload_to_image(volume.id,
                                               True,
                                               image_name,
                                               'bare',
                                               'qcow2')
    image_id = new_image[1]['os-volume_upload_image']['image_id']
    logging.info('Image:%s created, waiting' % image_id)
    result = wait_for_condition(glance.images.get, image_id,
                                ['active'], ['error'])
    if result is None:
        logging.error('Error creating image:%s, exiting'% image_id)
        return
    logging.info('Deleting created volume:%s' % volume.id)
    wait_for_condition(cinder.volumes.get, volume.id,
                       ['available'], ['error'])
    cinder.volumes.delete(volume.id)

    logging.info('Updating new image:%s' % image.id)
    old_image_args = vars(image)['_info']
    image_args = dict()
    image_args['name'] = old_image_args.pop('name', None)
    image_args['is_public'] = old_image_args.pop('is_public', None)
    glance.images.update(image_id, **image_args)

    if delete:
        logging.info('Deleting original image:%s' % image.id)
        glance.images.delete(image.id)
    new_size = glance.images.get(image_id).size
    return old_size - new_size

def shrink(args):
    glance = setup_glance(args)
    if args['all']:
        images = []
        for i in glance.images.list():
            images.append(i)
    else:
        images_list = args['image_id']
        images = []
        for i in images_list:
            images.append(glance.images.get(i))
    if images == None:
        logging.info('No images to convert')
        return
    size = 0
    for i in images:
        size += convert_image(args, i, delete=args['delete'])
    logging.info('Saved %d bytes (%f GB) of space' % (size, (size/GB)))

def parse_args():
    a = argparse.ArgumentParser(description='Shrink all raw images on a cluster')
    a.add_argument('--username', help='Auth username')
    a.add_argument('--password', help='Auth password')
    a.add_argument('--tenant-name', help='Auth tenant name')
    a.add_argument('--auth-url', help='Auth url')
    a.add_argument('--image-id', nargs='+', help='Id of image to convert')
    a.add_argument('--all', action='store_true', help='Convert all images')
    a.add_argument('--delete', action='store_true', help='Delete old images')
    return a.parse_args()

def get_env(args):
    pairs = {'username' : 'OS_USERNAME',
             'password' : 'OS_PASSWORD',
             'tenant_name' : 'OS_TENANT_NAME',
             'auth_url' : 'OS_AUTH_URL'
            }
    for k, v in pairs.iteritems():
        if args[k] == None and v in os.environ.keys():
            args[k] = os.environ[v]
    return args

def main():
    args = vars(parse_args())
    args = get_env(args)
    shrink(args)

if __name__ == '__main__':
    main()
