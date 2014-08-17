#!/usr/bin/env python
import argparse
import boto
from boto.s3 import connection as s3_connection
from boto.exception import S3ResponseError as s3_error
from keystoneclient.v2_0 import client as key_v2
import os
import sys
from urlparse import urlparse

def parse_args():
    p = argparse.ArgumentParser(description='S3 Command Line Tool For OpenStack')
    p.add_argument('--username', help='OpenStack Auth username')
    p.add_argument('--password', help='OpenStack Auth password')
    p.add_argument('--tenant-name', help='OpenStack Auth tenant name')
    p.add_argument('--auth-url', help='OpenStack Auth url')

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
    command_get.add_argument('key', help='Key name')
    command_get.add_argument('--file', help='File to save to')

    return p.parse_args()

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

def _get_boto_connection(args):
    keystone = key_v2.Client(username=args['username'],
                             password=args['password'],
                             tenant_name=args['tenant_name'],
                             auth_url=args['auth_url'])
    creds = keystone.ec2.list(keystone.user_id)
    if len(creds) == 0:
        keystone.ec2.create(keystone.user_id, keystone.tenant_id)
        creds = keystone.ec2.list(keystone.user_id)
    cred = creds[-1]
    s3_url = urlparse(keystone.service_catalog.url_for(service_type='object-store'))
    host, port = s3_url.netloc.split(':')
    return boto.connect_s3(aws_access_key_id=cred.access,
                           aws_secret_access_key=cred.secret,
                           host=host,
                           port=int(port),
                           is_secure=False,
                           calling_format=s3_connection.OrdinaryCallingFormat())

def _list(connection, bucket=None):
    if bucket is None:
        buckets = connection.get_all_buckets()
        bucket_list = '\n'.join(b.name for b in buckets)
        return bucket_list
    try:
        bucket = connection.get_bucket(bucket)
        key_list = '\n'.join(k.name for k in bucket.get_all_keys())
        return key_list
    except s3_error, s:
        return 'Error getting bucket:%s' % str(s)

def _create(connection, bucket, key=None, file_name=None, stringy=None):
    try:
        b = connection.get_bucket(bucket)
    except s3_error:
        b = connection.create_bucket(bucket)
    if key is not None:
        if b.get_key(key) is not None:
            return 'Key already exists'
        k = b.new_key(key_name=key)
        if file_name:
            full_name = os.path.abspath(file_name)
            with open(full_name, 'r') as f:
                k.set_contents_from_file(f)
        if stringy:
            k.set_contents_from_string(stringy)
        return 'Added key:%s' % key
    return 'Added bucket:%s' % bucket

def _delete(connection, bucket, key=None, force=False):
    if key:
        try:
            b = connection.get_bucket(bucket)
        except s3_error, s:
            return 'Cannot find bucket:%s' % str(s)
        b.delete_key(key)
        return 'Deleted key:%s' % key
    b = connection.get_bucket(bucket)
    key_list = b.get_all_keys()
    if force:
        for key in key_list:
            b.delete_key(key.name)
        key_list = b.get_all_keys()
    if len(key_list) == 0:
        connection.delete_bucket(bucket)
        return 'Deleted bucket:%s' % bucket
    return 'Cant delete bucket:%s, not empty' % bucket

def _get(connection, bucket, key, file_name=None):
    try:
        b = connection.get_bucket(bucket)
    except s3_error, s:
        return 'Cannot find bucket:%s' % str(s)
    try:
        k = b.get_key(key)
    except s3_error, s:
        return 'Cannot find key:%s' % str(s)
    if file_name:
        with open(file_name, 'w+') as f:
            f.write(k.get_contents_as_string())
        return 'File written to:%s' % file_name
    return k.get_contents_as_string()

def main():
    args = vars(parse_args())
    args = get_env(args)
    conn = _get_boto_connection(args)

    if args['command'] == 'list':
        print _list(conn,
                    bucket=args['bucket'],)

    if args['command'] == 'create':
        print _create(conn,
                      args['bucket'],
                      key=args['key'],
                      file_name=args['file'],
                      stringy=args['string'],)

    if args['command'] == 'delete':
        print _delete(conn,
                      args['bucket'],
                      key=args['key'],
                      force=args['force'],)

    if args['command'] == 'get':
        print _get(conn,
                   args['bucket'],
                   args['key'],
                   file_name=args['file'],)

if __name__ == '__main__':
    main()
