#!/usr/bin/env python
import argparse
import os
from prettytable import PrettyTable

from boyo.client import BoyoClient

def parse_args():
    p = argparse.ArgumentParser(description='S3 Command Line Tool For OpenStack')
    p.add_argument('--username', help='OpenStack Auth username')
    p.add_argument('--password', help='OpenStack Auth password')
    p.add_argument('--tenant_name', help='OpenStack Auth tenant name')
    p.add_argument('--auth_url', help='OpenStack Auth url')

    subparsers = p.add_subparsers(help='Command', dest='command')

    command_list = subparsers.add_parser('list', help='List buckets or keys')
    command_list.add_argument('bucket', nargs='?', help='Bucket name')

    command_create = subparsers.add_parser('create', help='Create a bucket or key')
    command_create.add_argument('bucket', help='Bucket name')
    command_create.add_argument('key', nargs='?', help='Key name')
    command_create.add_argument('--file', help='File to upload as key')
    command_create.add_argument('--string', help='String to upload as key')

    command_delete = subparsers.add_parser('delete', help='Delete a bucket or key')
    command_delete.add_argument('bucket', help='Bucket name')
    command_delete.add_argument('key', nargs='?', help='Key name')
    command_delete.add_argument('--force', '-f', action='store_true', help='Force')

    command_get = subparsers.add_parser('get', help='Get key')
    command_get.add_argument('bucket', help='Bucket name')
    command_get.add_argument('key', nargs='?', help='Key name')
    command_get.add_argument('--file', help='File to save to')

    return p.parse_args()

def get_env(args):
    if not args.username:
        args.username = os.getenv('OS_USERNAME')
    if not args.password:
        args.password = os.getenv('OS_PASSWORD')
    if not args.tenant_name:
        args.tenant_name = os.getenv('OS_TENANT_NAME')
    if not args.auth_url:
        args.auth_url = os.getenv('OS_AUTH_URL')
    return args

def main():
    args = get_env(parse_args())
    conn = BoyoClient(args.username, args.password,
                      args.tenant_name, args.auth_url)

    if args.command == 'list':
        buckets = conn.list(bucket_name=args.bucket,)
        if not buckets:
            print 'Result not found'
            return
        for bucket in buckets:
            print 'Bucket:', bucket.name
            table = PrettyTable(['name', 'size'])
            for key in bucket.keys:
                table.add_row([key.name, key.size])
            print table

    if args.command == 'create':
        obj = conn.create(args.bucket,
                          key_name=args.key,
                          file_name=args.file,
                          string_contents=args.string,)
        print obj.name

    if args.command == 'delete':
        result = conn.delete(args.bucket,
                             key_name=args.key,
                             force=args.force,)
        if result:
            print 'Deleted'
        else:
            print 'Not deleted'

    if args.command == 'get':
        result = conn.get(args.bucket,
                          key_name=args.key,
                          file_name=args.file,)
        if result:
            print result
