#!/usr/bin/env python
import boto
from boto.s3 import connection as s3_connection
from boto.exception import S3ResponseError as s3_error
from keystoneclient.v2_0 import client as key_v2
import logging
import os
from urlparse import urlparse

log = logging.getLogger(__name__)

class BoyoClient(object):
    def __init__(self, username, password, tenant_name, auth_url):
        keystone = key_v2.Client(username=username,
                                 password=password,
                                 tenant_name=tenant_name,
                                 auth_url=auth_url)
        creds = keystone.ec2.list(keystone.user_id)
        if len(creds) == 0:
            keystone.ec2.create(keystone.user_id, keystone.tenant_id)
            creds = keystone.ec2.list(keystone.user_id)
        cred = creds[-1]
        s3_url = urlparse(keystone.service_catalog.url_for(service_type='object-store'))
        host, port = s3_url.netloc.split(':')
        self.boto = boto.connect_s3(aws_access_key_id=cred.access,
                                    aws_secret_access_key=cred.secret,
                                    host=host,
                                    port=int(port),
                                    is_secure=False,
                                    calling_format=s3_connection.OrdinaryCallingFormat())

    def list(self, bucket_name=None):
        log.debug('Getting list for bucket:%s' % bucket_name)
        if bucket_name:
            try:
                buckets = [self.boto.get_bucket(bucket_name)]
            except s3_error, e:
                log.Error('Error getting bucket:%s' % e)
                return None
        else:
            try:
                buckets = self.boto.get_all_buckets()
            except s3_error, e:
                log.error('Error getting buckets:%s' % e)
                return None
            log.debug('Found buckets:%s' % buckets)
        if buckets != []:
            for b in buckets:
                log.debug('Getting keys for bucket:%s' % b.name)
                b.keys = b.get_all_keys()
        return buckets

    def create(self, bucket_name, key_name=None, file_name=None, stringy=None):
        log.debug('Checking for bucket:%s' % bucket_name)
        try:
            bucket = self.boto.get_bucket(bucket_name)
            log.debug('Bucket exists')
        except s3_error, e:
            log.debug('Creating bucket:%s' % e)
            bucket = self.boto.create_bucket(bucket_name)

        if key_name:
            log.debug('Checking for key:%s' % key_name)
            if bucket.get_key(key_name):
                log.debug('Key already exists, will not replace')
                return None
            log.debug('Creating key:%s' % key_name)
            key = bucket.new_key(key_name=key_name)

            if file_name:
                log.debug('Loading contents from file:%s' % file_name)
                full_name = os.path.abspath(file_name)
                with open(full_name, 'r') as f:
                    key.set_contents_from_file(f)
            elif stringy:
                log.debug('Setting contents from string:%s' % stringy)
                key.set_contents_from_string(stringy)
            return key
        return bucket

    def delete(self, bucket_name, key_name=None, force=False):
        log.debug('Checking for bucket:%s' % bucket_name)
        try:
            bucket = self.boto.get_bucket(bucket_name)
        except s3_error:
            log.error('Error finding bucket:%s' % bucket_name)
            return False
        if key_name:
            log.debug('Deleting key:%s' % key_name)
            try:
                bucket.delete_key(key_name)
            except s3_error, e:
                log.error('Error deleting key:%s' % e)
                return False
            return True
        log.debug('Gathering keys for bucket:%s' % bucket_name)
        keys = bucket.get_all_keys()
        delete_bucket = False
        if keys == []:
            log.debug('No keys in bucket, deleting')
            delete_bucket = True
        elif force:
            log.debug('Keys exist, but force specified, deleting keys first')
            for key in key:
                log.debug('Deleting key:%s' % key.name)
                try:
                    bucket.delete_key(key.name)
                except s3_error, s:
                    log.error('Error deleting key:%s' % s)
                    return False
            delete_bucket = True
        if delete_bucket:
            log.debug('Deleting bucket:%s' % bucket_name)
            self.boto.delete_bucket(bucket_name)
            return True
        return False

    def get(self, bucket_name, key_name, file_name=None):
        log.debug('Getting bucket:%s' % bucket_name)
        try:
            bucket = self.boto.get_bucket(bucket_name)
        except s3_error, s:
            log.error('Cannot find bucket:%s' % s)
            return None
        log.debug('Getting key:%s' % key_name)
        try:
            key = bucket.get_key(key_name)
        except s3_error, s:
            log.error('Cannot find key:%s' % s)
            return None
        if file_name:
            log.debug('Writing contents to file:%s' % file_name)
            with open(file_name, 'w+') as f:
                f.write(key.get_contents_as_string())
            return None
        log.debug('Returning contents as string')
        return key.get_contents_as_string()
