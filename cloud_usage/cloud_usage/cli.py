#!/usr/bin/env python

from cloud_usage.client import CloudUsage

import argparse
import logging
import os
from prettytable import PrettyTable
import sys


log_format = '%(asctime)s-%(levelname)s-%(message)s'
log = logging.getLogger('cloud_usage')
log.setLevel(logging.DEBUG)
handle = logging.StreamHandler()
handle.setLevel(logging.ERROR)
form = logging.Formatter(log_format)
handle.setFormatter(form)
log.addHandler(handle)

def parse_args():
    p = argparse.ArgumentParser(description='Create & Setup OpenStack Accounts')
    p.add_argument('--username', help='OpenStack Auth username')
    p.add_argument('--password', help='OpenStack Auth password')
    p.add_argument('--tenant_name', help='OpenStack Auth tenant name')
    p.add_argument('--auth_url', help='OpenStack Auth keystone url')
    return p.parse_args()

def get_env_args(args):
    # Check environment for variables if not set on command line
    if not args.username:
        args.username = os.getenv('OS_USERNAME')
    if not args.password:
        args.password = os.getenv('OS_PASSWORD')
    if not args.tenant_name:
        args.tenant_name = os.getenv('OS_TENANT_NAME')
    if not args.auth_url:
        args.auth_url = os.getenv('OS_AUTH_URL')
    must_have = ['username', 'password', 'tenant_name', 'auth_url']
    for item in must_have:
        if getattr(args, item) == None:
            sys.exit("Don't have:%s, exiting" % item)
    return args

def main():
    args = get_env_args(parse_args())
    c = CloudUsage(args.username, args.password,
                   args.tenant_name, args.auth_url)

    data = c.cloud_usage()
    show_keys = data.keys()
    for key in show_keys:
        print 'Module --', key
        raw_columns = data[key]['total'].keys()
        columns = ['tenant'] + raw_columns
        table = PrettyTable(columns)
        for tenant, value in data[key].iteritems():
            row = [tenant]
            for c in raw_columns:
                row.append(value[c])
            table.add_row(row)
        print table

if __name__ == '__main__':
    main()
