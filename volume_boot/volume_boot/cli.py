#!/usr/bin/env python

from volume_boot import VolumeBoot
import argparse
import logging
import os
import sys

log_format = '%(asctime)s-%(levelname)s-%(message)s'
log = logging.getLogger('volume_boot')
log.setLevel(logging.DEBUG)
handle = logging.StreamHandler()
handle.setLevel(logging.DEBUG)
form = logging.Formatter(log_format)
handle.setFormatter(form)
log.addHandler(handle)


def parse_args():
    p = argparse.ArgumentParser(description='Manage Boot From Volume Instances')
    p.add_argument('--username', help='OpenStack Auth username')
    p.add_argument('--password', help='OpenStack Auth password')
    p.add_argument('--tenant-name', help='OpenStack Auth tenant name')
    p.add_argument('--auth-url', help='OpenStack Auth keystone url')

    subparsers = p.add_subparsers(help='Sub-command', dest='command')

    boot = subparsers.add_parser('boot',
                                 help='Create instance from bootable volume')
    boot.add_argument('flavor', help='ID of flavor')
    boot.add_argument('image', help='ID of image')
    boot.add_argument('name', help='Name of new instance')
    boot.add_argument('size', type=int, help='Size of volume')
    boot.add_argument('--key-name', help='Name of keypair to use')
    boot.add_argument('--no-temp', action='store_true',
                      help='Do not use keypair injection workaround')
    boot.add_argument('--temp-flavor',
                      default='1',
                      help='Temp flavor to use for key injection')
    boot.add_argument('--volume-type',
                      help='Volume type for created volume')
    boot.add_argument('--networks', nargs='+', help='Network IDS')
    boot.add_argument('--security-groups', nargs='+', help='Security groups')

    snapshot = subparsers.add_parser('snapshot', help='Snapshot instance')
    snapshot.add_argument('instance', help='ID of instance')
    snapshot.add_argument('--name', help='Image name')

    backup = subparsers.add_parser('backup', help='Backup instance')
    backup.add_argument('instance', help='ID of instance')
    backup.add_argument('--max', default=0, type=int,
                        help='Maximum number of backups')
    backup.add_argument('--swift', action='store_true',
                        help='Convert image to swift')
    backup.add_argument('--direct', action='store_true',
                        help='Move directly from glance to swift')
    backup.add_argument('--compress', action='store_true',
                        help='Compress a swift object')
    return p.parse_args()

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
    v = VolumeBoot(args['username'], args['password'],
                   args['tenant_name'], args['auth_url'])
    if args['command'] == 'boot':
        v.boot_from_volume(args['flavor'], args['image'], args['name'],
                           args['size'], args['temp_flavor'],
                           key_name=args['key_name'],
                           volume_type=args['volume_type'],
                           networks=args['networks'],
                           security_groups=args['security_groups'],
                           no_temp=args['no_temp'])
    if args['command'] == 'snapshot':
        v.snapshot_instance(args['instance'], image_name=args['name'])
    if args['command'] == 'backup':
        v.backup_instance(args['instance'], args['max'],
                          swift=args['swift'], compress=args['compress'],
                          direct=args['direct'])

if __name__ == '__main__':
    main()
