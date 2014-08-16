#!/usr/bin/env python

import argparse
import os
from shrink_image import ShrinkImage
import sys

def parse_args():
    p = argparse.ArgumentParser(description='Manage Boot From Volume Instances')
    p.add_argument('--username', help='OpenStack Auth username')
    p.add_argument('--password', help='OpenStack Auth password')
    p.add_argument('--tenant-name', help='OpenStack Auth tenant name')
    p.add_argument('--auth-url', help='OpenStack Auth keystone url')

    p.add_argument('image_id', nargs='?', help='Image_id')
    p.add_argument('--name', help='Image name')
    p.add_argument('--all', action='store_true',
                   help='Convert all images')

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

    s = ShrinkImage(args['username'], args['password'], args['tenant_name'],
                    args['auth_url'])
    if args['all']:
        s.shrink_all_images()
    if args['image_id']:
        s.shrink_image(args['image_id'], image_name=args['name'])

if __name__ == '__main__':
    main()
