#!/usr/bin/env python
import argparse
from cinderclient.v1 import client as cinder_v1
import code
from novaclient.v1_1 import client as nova_v1
from novaclient.shell import OpenStackComputeShell as open_shell
from glanceclient import Client as glance_client
from keystoneclient.v2_0 import client as key_v2
from neutronclient.v2_0 import client as neutron_v2
import os
import swiftclient
import sys

def parse_args():
    a = argparse.ArgumentParser(description='Give me the api clients')
    a.add_argument('--username', help='Auth username')
    a.add_argument('--password', help='Auth password')
    a.add_argument('--tenant-name', help='Auth tenant name')
    a.add_argument('--auth-url', help='Auth url')
    return a.parse_args()

def get_env(args):
    if args['username'] == None and 'OS_USERNAME' in os.environ.keys():
        args['username'] = os.environ['OS_USERNAME']
    if args['password'] == None and 'OS_PASSWORD' in os.environ.keys():
        args['password'] = os.environ['OS_PASSWORD']
    if args['tenant_name'] == None and 'OS_TENANT_NAME' in os.environ.keys():
        args['tenant_name'] = os.environ['OS_TENANT_NAME']
    if args['auth_url'] == None and 'OS_AUTH_URL' in os.environ.keys():
        args['auth_url'] = os.environ['OS_AUTH_URL']
    must_have = ['username', 'password', 'tenant_name', 'auth_url']
    for item in must_have:
        if args[item] == None:
            sys.exit("Don't have:%s, exiting" % item)
    return args

def main():
    args = vars(parse_args())
    args = get_env(args)
    extensions = open_shell()._discover_extensions("1.1")
    nova = nova_v1.Client(args['username'],
                          args['password'],
                          args['tenant_name'],
                          args['auth_url'],
                          extensions=extensions)
    keystone = key_v2.Client(username=args['username'],
                             password=args['password'],
                             tenant_name=args['tenant_name'],
                             auth_url=args['auth_url'])
    neutron = neutron_v2.Client(username=args['username'],
                                password=args['password'],
                                tenant_name=args['tenant_name'],
                                auth_url=args['auth_url'])
    cinder = cinder_v1.Client(args['username'],
                              args['password'],
                              args['tenant_name'],
                              args['auth_url'])
    swift = swiftclient.client.Connection(auth_version='2',
                                          user=args['username'],
                                          key=args['password'],
                                          tenant_name=args['tenant_name'],
                                          authurl=args['auth_url'])
    token = keystone.auth_token
    service_catalog = keystone.service_catalog
    catalog = service_catalog.catalog['serviceCatalog']
    glance_ip = None
    for endpoint in catalog:
        if 'image' == endpoint['type']:
            glance_ip = endpoint['endpoints'][0]['publicURL']
    glance = glance_client('1', endpoint=glance_ip, token=token)
    code.interact(local=locals())
if __name__ == '__main__':
    main()
