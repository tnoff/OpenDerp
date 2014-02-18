#!/usr/bin/env python
import argparse
from cinderclient.v1 import client as cinder_v1
import code
from novaclient.v1_1 import client as nova_v1
from novaclient.shell import OpenStackComputeShell as open_shell
from glanceclient import Client as glance_client
from keystoneclient.v2_0 import client as key_v2
from neutronclient.v2_0 import client as neutron_v2
import swiftclient

def parse_args():
    a = argparse.ArgumentParser(description='Give me the api clients')
    a.add_argument('username', help='Auth username')
    a.add_argument('password', help='Auth password')
    a.add_argument('tenant_name', help='Auth tenant name')
    a.add_argument('auth_url', help='Auth url')
    return a.parse_args()

def main():
    args = parse_args()
    extensions = open_shell()._discover_extensions("1.1")
    nova = nova_v1.Client(args.username,
                          args.password,
                          args.tenant_name,
                          args.auth_url,
                          extensions=extensions)
    keystone = key_v2.Client(username=args.username,
                             password=args.password,
                             tenant_name=args.tenant_name,
                             auth_url=args.auth_url)
    neutron = neutron_v2.Client(username=args.username,
                                password=args.password,
                                tenant_name=args.tenant_name,
                                auth_url=args.auth_url)
    cinder = cinder_v1.Client(args.username,
                              args.password,
                              args.tenant_name,
                              args.auth_url)
    swift = swiftclient.client.Connection(auth_version='2', user=args.username, 
                                          key=args.password, tenant_name=args.tenant_name, 
                                          authurl=args.auth_url)
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
