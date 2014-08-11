#!/usr/bin/env python
import argparse

def write_file(args, file_name):
    text = '#!/bin/bash\n'
    text += 'export OS_AUTH_URL=%s\n' % args['auth_url']
    text += 'export OS_TENANT_NAME=%s\n' % args['tenant_name']
    text += 'export OS_USERNAME=%s\n' % args['username']
    text += 'echo "Please enter your OpenStack password:"\n'
    text += 'read -s OS_PASSWORD_INPUT\n'
    text += 'export OS_PASSWORD=$OS_PASSWORD_INPUT\n'
    with open(file_name, 'w+') as f:
        f.write(text)

def parse_args():
    p = argparse.ArgumentParser(description='Make an OpenStack source file')
    p.add_argument('username', help='Auth username')
    p.add_argument('tenant_name', help='Auth tenant name')
    p.add_argument('auth_url', help='Auth url')
    p.add_argument('file_name', help='File name')
    return p.parse_args()

def main():
    args = vars(parse_args())
    file_name = args.pop('file_name')
    write_file(args, file_name)

if __name__ == '__main__':
    main()
