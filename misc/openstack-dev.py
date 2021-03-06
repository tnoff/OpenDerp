#!/usr/bin/env python
import argparse
import boto
from boto.s3 import connection as s3_connection
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
from urlparse import urlparse

def parse_args():
    a = argparse.ArgumentParser(description='Give me the api clients')
    a.add_argument('--username', help='Auth username')
    a.add_argument('--password', help='Auth password')
    a.add_argument('--tenant-name', help='Auth tenant name')
    a.add_argument('--auth-url', help='Auth url')
    a.add_argument('--ca-cert', help='Ca cert file')
    return a.parse_args()

def get_env(args):
    if not args['username']:
        args['username'] = os.getenv('OS_USERNAME', None)
    if not args['password']:
        args['password'] = os.getenv('OS_PASSWORD', None)
    if not args['tenant_name']:
        args['tenant_name'] = os.getenv('OS_TENANT_NAME', None)
    if not args['auth_url']:
        args['auth_url'] = os.getenv('OS_AUTH_URL', None)
    if not args['ca_cert']:
        args['ca_cert'] = os.getenv('OS_CACERT')
    # Check for args
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
                          extensions=extensions,
                          cacert=args['ca_cert'])
    keystone = key_v2.Client(username=args['username'],
                             password=args['password'],
                             tenant_name=args['tenant_name'],
                             auth_url=args['auth_url'],
                             cacert=args['ca_cert'],)
    neutron = neutron_v2.Client(username=args['username'],
                                password=args['password'],
                                tenant_name=args['tenant_name'],
                                auth_url=args['auth_url'],
                                cacert=args['ca_cert'],)
    cinder = cinder_v1.Client(args['username'],
                              args['password'],
                              args['tenant_name'],
                              args['auth_url'],
                              cacert=args['ca_cert'],)
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

    creds = keystone.ec2.list(keystone.user_id)
    if len(creds) == 0:
        keystone.ec2.create(keystone.user_id, keystone.tenant_id)
        creds = keystone.ec2.list(keystone.user_id)
    cred = creds[-1]
    s3_url = urlparse(keystone.service_catalog.url_for(service_type='object-store'))
    host, port = s3_url.netloc.split(':')
    s3 = boto.connect_s3(aws_access_key_id=cred.access,
                         aws_secret_access_key=cred.secret,
                         host=host,
                         port=int(port),
                         is_secure=False,
                         calling_format=s3_connection.OrdinaryCallingFormat())
    code.interact(local=locals())

if __name__ == '__main__':
    main()
