#!/usr/bin/env python
import argparse
from cinderclient.v1 import client as cinder_v1
from datetime import datetime
from glanceclient import Client as glance_client
import json
from keystoneclient.v2_0 import client as key_v2
import logging
from novaclient.v1_1 import client as nova_v1
import os
import random
import string
import sys
import time

logging_format = '%(asctime)s--%(levelname)s--%(message)s'
logging.basicConfig(format=logging_format, level=logging.INFO)
log = logging.getLogger(__name__)

def _random_string(prefix='', length=10):
    characters = string.ascii_lowercase + string.digits
    s = ''.join(random.choice(characters) for _ in range(length))
    return prefix + s

def _wait_for_condition(check_function, item_id, whitelist, blacklist,
                        timeout=3600):
    obj = check_function(item_id)
    start = time.time()
    while obj.status not in whitelist:
        if time.time() - start >= timeout:
            return None
        if obj.status in blacklist:
            return None
        obj = check_function(item_id)
        time.sleep(60)
    return obj.id

def _wait_for_deletion(list_function, item_id, blacklist, timeout=3600):
    start = time.time()
    while time.time() - start >= timeout:
        found = False
        for i in list_function:
            if i.id == item_id:
                found = True
                if i.status in blacklist:
                    return False
                break
        if not found:
            return True
    return False

def _get_glance_client(username, password, tenant_name, auth_url):
    keystone = key_v2.Client(username=username,
                             password=password,
                             tenant_name=tenant_name,
                             auth_url=auth_url)
    token = keystone.auth_token
    catalog = keystone.service_catalog.catalog['serviceCatalog']
    glance_ip = None
    for endpoint in catalog:
        if 'image' == endpoint['type']:
            glance_ip = endpoint['endpoints'][0]['publicURL']
    return glance_client('1', endpoint=glance_ip, token=token)

def _create_keypair_image(nova, glance, image_id, key_name, dummy_flavor):
    # OpenStack does not support key injection on instances booted from volume
    # To workaround this, create a dummy instance with the keypair
    # Snapshot this instance, and then create a volume from that snapshot
    # The snapshot will contain the injected key
    server_name = _random_string(prefix='dummy-')
    log.info('Creating dummy server')
    server = nova.servers.create(server_name, image_id,
                                 dummy_flavor, key_name=key_name)
    log.info('Server created:%s' % server.id)
    log.info('Waiting for server:%s' % server.id)
    result = _wait_for_condition(nova.servers.get, server.id,
                                 ['ACTIVE'], ['ERROR'])
    if result == None:
        sys.exit('Error creating keypair server, exiting :(')
    log.info('Stopping server:%s' % server.id)
    nova.servers.stop(server.id)
    result = _wait_for_condition(nova.servers.get, server.id,
                                 ['SHUTOFF'], ['ERROR'])
    log.info('Server:%s stopped, continue' % server.id)
    if result == None:
        sys.exit('Error stopping server, exiting :(')
    log.info('Creating dummy snapshot of server:%s' % server.id)
    image_name = _random_string(prefix='dummy-')
    image_id = nova.servers.create_image(server.id, image_name)
    log.info('Image:%s created, waiting' % image_id)
    result = _wait_for_condition(nova.images.get, image_id,
                                 ['ACTIVE'], ['ERROR'])
    log.info('Deleting dummy server:%s' % server.id)
    nova.servers.delete(server.id)
    image = glance.images.get(image_id)
    return image

def _shrink_image(cinder, nova, glance, image):
    # To shrink an image, create a volume from that image
    # then create a qcow2 image from that volume
    # The cinder backend will do a 'qemu-img convert' to shrink the image
    real_size = image.size / (1024*1024*1024.0)
    log.info('Image:%s not large enough, shrinking' % image.id)
    vol = cinder.volumes.create(real_size + 1, imageRef=image.id)
    log.info('Volume created:%s, waiting' % vol.id)
    result = _wait_for_condition(cinder.volumes.get, vol.id,
                                 ['available'], ['error'])
    log.info('Volume:%s created, converted back into image' % vol.id)
    if result == None:
        sys.exit('Error creating volume, exiting :(')
    log.info('Deleting old dummy image:%s' % image.id)
    glance.images.delete(image.id)
    image_name = _random_string(prefix='dummy')
    log.info('Creating shurnk image from volume:%s' % vol.id)
    image = cinder.volumes.upload_to_image(vol.id, True,
                                           image_name, 'bare', 'qcow2')
    image_id = image[1]['os-volume_upload_image']['image_id']
    log.info('Waiting for new image:%s' % image_id)
    result = _wait_for_condition(nova.images.get, image_id,
                                 ['ACTIVE'], ['ERROR'])
    if result == None:
        sys.exit('Error creating volume, exiting :(')
    log.info('New image created:%s, checking size' % image_id)
    image = glance.images.get(image_id)
    real_size = image.size / (1024*1024*1024.0)
    log.info('Creating dummy volume:%s' % vol.id)
    cinder.volumes.delete(vol.id)
    return image

def _launch_server(glance, cinder, nova,
                   image_id, flavor_id, vol_size, server_name,
                   volume_type, networks):
    # You cannot create a bootable volume that is smaller than the image
    # So check if you need to shrink the image
    image = glance.images.get(image_id)
    real_size = image.size /(1024*1024*1024.0)
    if vol_size < real_size:
        image = _shrink_image(cinder, nova, glance, image)
        real_size = image.size / (1024*1024*1024.0)
        if vol_size < real_size:
            sys.exit('Your volume size isnt big enough, need:%s GB' % real_size)
        image_id = image.id

    # Once size is ok, create the bootable volume
    log.info('Creating bootable volume')
    vol = cinder.volumes.create(vol_size, imageRef=image_id,
                                volume_type=volume_type)
    log.info("Volume created:%s, waiting" % vol.id)
    result = _wait_for_condition(cinder.volumes.get, vol.id,
                                 ['available'], ['error'])
    if result == None:
        sys.exit('Your volume cant boot, exiting :(')

    # Then boot the server
    log.info('Volume avaialable:%s, booting server' % vol.id)
    if server_name == None:
        server_name = _random_string(prefix='server-')
    block_mapping = {'vda' : '%s:::0' % str(vol.id)}
    # Check networks
    nic = None
    if networks:
        nic = []
        for net in networks:
            nic.append({'net-id' : net})
    server = nova.servers.create(server_name, image_id, flavor_id,
                                 block_device_mapping=block_mapping, nics=nic)
    log.info('Server:%s created, waiting' % server.id)
    result = _wait_for_condition(nova.servers.get, server.id,
                                 ['ACTIVE'], ['ERROR'])
    if result == None:
        log.error('Error creating server:%s, exiting' % server.id)
        sys.exit()
    log.info('Server ready:%s' % server.id)

def boot_server(args):
    glance = _get_glance_client(args['os_username'], args['os_password'],
                                args['os_tenant_name'], args['os_auth_url'])
    cinder = cinder_v1.Client(args['os_username'], args['os_password'],
                              args['os_tenant_name'], args['os_auth_url'])
    nova = nova_v1.Client(args['os_username'], args['os_password'],
                          args['os_tenant_name'], args['os_auth_url'])

    delete_image = False
    if args['key_name'] != None:
        image = _create_keypair_image(nova, glance, args['image-id'],
                                      args['key_name'], args['dummy_flavor'])
        args['image-id'] = image.id
        # You can keep the keypair injected image if you choose
        # Delete by default
        if not args['keep_image']:
            delete_image = True
    _launch_server(glance, cinder, nova, args['image-id'], args['flavor-id'],
                   args['vol-size'], args['name'], args['volume_type'],
                   args['networks'])
    if delete_image:
        glance.images.delete(args['image-id'])

def snapshot_server(args):
    glance = _get_glance_client(args['os_username'], args['os_password'],
                                args['os_tenant_name'], args['os_auth_url'])
    cinder = cinder_v1.Client(args['os_username'], args['os_password'],
                              args['os_tenant_name'], args['os_auth_url'])
    nova = nova_v1.Client(args['os_username'], args['os_password'],
                          args['os_tenant_name'], args['os_auth_url'])
    # When you create a snapshot from a volume, it returns an image
    # This image is useless, it only points you to a volume snapshot
    # Use this volume snapshot to create a save image
    dummy_image_name = _random_string(prefix='dummy-')
    log.info('Snapshotting server:%s' % args['instance-id'])
    image_id = nova.servers.create_image(args['instance-id'], dummy_image_name)
    image = glance.images.get(image_id)
    log.info('Created useless image:%s' % image_id)
    mappings = json.loads(image.properties['block_device_mapping'])
    # Find the volume snapshot in the image metadata
    volume_snap = None
    for m in mappings:
        if m['instance_uuid'] == args['instance-id']:
            volume_snap = m['snapshot_id']
    if volume_snap == None:
        log.error('Cannot find volume snapshot, exiting')
        return
    log.info('Volume snapshot found, deleting useless image')
    glance.images.delete(image_id)
    log.info('Volume snapshot:%s' % volume_snap)
    # Make sure volume snapshot is useable
    volume_snapshot = cinder.volume_snapshots.get(volume_snap)
    result = _wait_for_condition(cinder.volume_snapshots.get, volume_snap,
                                 ['available'], ['error'])
    if result is None:
        log.error('Error creating volume snapshot')
        sys.exit()
    # Create a volume from that snasphot
    vol = cinder.volumes.create(volume_snapshot.size,
                                snapshot_id=volume_snap)
    log.info('Created volume:%s, waiting' % vol.id)
    result = _wait_for_condition(cinder.volumes.get, vol.id,
                                 ['available'], ['error'])
    if result is None:
        log.error('Error creating volume:%s' % vol.id)
        sys.exit()
    if args['image_name'] == None:
        args['image_name'] = 'Snapshot of instance:%s' % args['instance-id']
    # Create a image from that volume
    im = cinder.volumes.upload_to_image(vol.id, True,
                                        args['image_name'], 'bare', 'qcow2')
    image_id = im[1]['os-volume_upload_image']['image_id']
    log.info('Created image:%s, waiting' % image_id)
    result = _wait_for_condition(glance.images.get, image_id,
                                 ['active'], ['error'])
    if result is None:
        log.error('Error creating image:%s' % image_id)
        sys.exit()
    # Delete all the things once the image is made
    cinder.volumes.delete(vol.id)
    result = _wait_for_deletion(cinder.volumes.list, vol.id, ['error'])
    if result is None:
        log.error('Error deleting volume:%s' % vol.id)
    cinder.volume_snapshots.delete(volume_snap)
    if args['download'] != None:
        log.info('Downloading image:%s' % image_id)
        with open(args['download'], 'w+') as f:
            for d in glance.images.data(image_id, do_checksum=False):
                f.write(d)
    return image_id

def _find_oldest_backup(glance, instance_id):
    backup_num = 0
    oldest_image = None
    oldest_time = None
    for im in glance.images.list():
        try:
            if im.properties['backup_instance_uuid'] == instance_id:
                backup_num += 1
                if oldest_time == None:
                    oldest_image = im.id
                    oldest_time = im.properties['backup_timestamp']
                elif im.properties['backup_timestamp'] < oldest_time:
                    oldest_image = im.id
                    oldest_time = im.properties['backup_timestamp']
        except KeyError:
            continue
    return oldest_image, backup_num

def backup(args):
    # Snapshot a server, and keep a certain number of backups in glance
    args['image_name'] = args['instance-id'] + '-' + str(datetime.utcnow())
    args['download'] = None
    image_id = snapshot_server(args)
    glance = _get_glance_client(args['os_username'], args['os_password'],
                                args['os_tenant_name'], args['os_auth_url'])
    image = glance.images.get(image_id)
    properties = image.properties
    # Set metadata to make image easier to find
    properties['backup_instance_uuid'] = args['instance-id']
    properties['backup_timestamp'] = time.time()
    log.info("Updating image:%s to have backup info" % image_id)
    glance.images.update(image_id, properties=properties)
    # Check if any old backups need deletion
    while True:
        oldest_image, backup_num = _find_oldest_backup(glance,
                                                       args['instance-id'])
        if backup_num <= args['backups']:
            break
        log.info("Deleting oldest image:%s" % oldest_image)
        glance.images.delete(oldest_image)

def parse_args():
    a = argparse.ArgumentParser(
        description='Create a ceph backed instance from an image')
    a.add_argument('--os-username', help='OpenStack Auth username')
    a.add_argument('--os-password', help='OpenStack Auth password')
    a.add_argument('--os-tenant-name', help='OpenStack Auth tenant name')
    a.add_argument('--os-auth-url', help='OpenStack Auth keystone url')

    subparser = a.add_subparsers(dest='command')
    boot = subparser.add_parser('boot', help='Boot a new instance')

    boot.add_argument('image-id', help='ID of image to use')
    boot.add_argument('flavor-id', help='ID of flavor to use')
    boot.add_argument('vol-size', type=int, help='Size of volume in GB')
    boot.add_argument('--name', help='Name of instance')
    boot.add_argument('--key-name', help='Name of key to use')
    boot.add_argument('--keep-image', action='store_true',
                      help='Keep injected keypair image')
    boot.add_argument('--volume-type', default='ceph', help='Volume type')
    boot.add_argument('--networks', nargs='+',
                      help='Network IDs to add to instance')
    # This should be the smallest flavor possible
    # You want an instance booted from this flavor to launch very quickly
    boot.add_argument('--dummy-flavor', default='1',
                      help='Flavor to launch dummy instances with')

    snapshot = subparser.add_parser('snapshot', help='Snapshot an instance')
    snapshot.add_argument('instance-id', help='ID of instance to snapshot')
    snapshot.add_argument('--image-name', help='Name of new image')
    snapshot.add_argument('--download', help='Download new image')

    back = subparser.add_parser('backup', help='Backup an instance')
    back.add_argument('instance-id', help='ID of instance to backup')
    back.add_argument('--backups', type=int, default=5,
                      help='Number of backups to keep')


    return a.parse_args()

def get_env_args(args):
    # Check environment for variables if not set on command line
    if not args['username']:
        args['username'] = os.getenv('OS_USERNAME', None)
    if not args['password']:
        args['password'] = os.getenv('OS_PASSWORD', None)
    if not args['tenant_name']:
        args['tenant_name'] = os.getenv('OS_TENANT_NAME', None)
    if not args['auth_url']:
        args['auth_url'] = os.getenv('OS_AUTH_URL', None)
    must_have = ['username', 'password', 'tenant_name', 'auth_url']
    for item in must_have:
        if args[item] == None:
            sys.exit("Don't have:%s, exiting" % item)
    return args

def main():
    args = vars(parse_args())
    args = get_env_args(args)
    if args['command'] == 'boot':
        boot_server(args)
    if args['command'] == 'snapshot':
        snapshot_server(args)
    if args['command'] == 'backup':
        backup(args)

if __name__ == '__main__':
    main()
