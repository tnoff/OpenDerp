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
        '''Args correspond to OpenStack auth args'''
        # Get "ec2" creds from keystone
        keystone = key_v2.Client(username=username,
                                 password=password,
                                 tenant_name=tenant_name,
                                 auth_url=auth_url)
        creds = keystone.ec2.list(keystone.user_id)
        if len(creds) == 0:
            keystone.ec2.create(keystone.user_id, keystone.tenant_id)
            creds = keystone.ec2.list(keystone.user_id)
        cred = creds[-1]
        # use to create s3 connection
        s3_url = urlparse(keystone.service_catalog.url_for(
                    service_type='object-store'))
        host, port = s3_url.netloc.split(':')
        self.boto = boto.connect_s3(aws_access_key_id=cred.access,
                                    aws_secret_access_key=cred.secret,
                                    host=host,
                                    port=int(port),
                                    is_secure=False,
                                    calling_format=s3_connection.OrdinaryCallingFormat())

    def list(self, bucket_name=None):
        '''
        List buckets and their objects
        If bucket name specified, give only that bucket in list
        Keys can be called with bucket.keys
        '''
        log.debug('Bucket name given:%s' % bucket_name)
        if bucket_name:
            log.info('Retrieving bucket:%s' % bucket_name)
            try:
                buckets = [self.boto.get_bucket(bucket_name)]
            except s3_error, e:
                log.error('Error getting bucket:%s' % str(e))
                return None
        else:
            log.info("Retreiving all buckets")
            try:
                buckets = self.boto.get_all_buckets()
                log.debug('Found buckets:%s' % buckets)
            except s3_error, e:
                log.error('Error getting buckets:%s' % str(e))
                return None
        # Get keys for all buckets
        if buckets:
            log.info('Getting keys for all buckets:%s' % str(buckets))
            for b in buckets:
                log.debug('Getting keys for bucket:%s' % b.name)
                b.keys = b.get_all_keys()
        return buckets

    def create(self, bucket_name, key_name=None, file_name=None,
               string_contents=None):
        '''
        Attempt to create bucket with name, also key_name if given
        Key can be created without file or string_contents, but key will be
        blank and useless
        '''
        log.info('Checking if bucket:%s exists' % bucket_name)
        try:
            bucket = self.boto.get_bucket(bucket_name)
            log.info('Bucket:%s exists' % bucket_name)
        except s3_error, e:
            log.debug('Cannot create bucket:%s' % str(e))
            log.info('Bucket cannot be found, creating bucket:%s' % bucket_name)
            bucket = self.boto.create_bucket(bucket_name)
        # If no key given done, exit
        if not key_name:
            return bucket
        # Else begin logic for creating key
        log.info('Checking if key:%s exists in bucket:%s' % (key_name,
                                                             bucket.name))
        key = bucket.get_key(key_name)
        if key:
            log.info('Key:%s already exists, will not replace' % key_name)
            return key
        log.info('Key does not exist, creating key:%s' % key_name)
        key = bucket.new_key(key_name=key_name)

        if file_name:
            log.info('Loading contents from file:%s' % file_name)
            full_name = os.path.abspath(file_name)
            with open(full_name, 'r') as f:
                key.set_contents_from_file(f)
        elif string_contents:
            log.info('Setting contents from string:%s' % string_contents)
            key.set_contents_from_string(string_contents)
        return key

    def delete(self, bucket_name, key_name=None, force=False):
        '''
        If bucket and key given, delete key
        If only bucket given, delete bucket
        If force used on deleting bucket, all keys will be removed first
        '''
        log.info('Checking if bucket:%s exists' % bucket_name)
        try:
            bucket = self.boto.get_bucket(bucket_name)
            log.info('Bucket:%s exists' % bucket_name)
        except s3_error:
            log.error('Error finding bucket:%s' % bucket_name)
            return False
        # If key name given, try and delete key
        if key_name:
            log.info('Attempting to delete key:%s' % key_name)
            try:
                bucket.delete_key(key_name)
            except s3_error, e:
                log.error('Error deleting key:%s' % str(e))
                return False
            return True
        # Else start logic for deleting bucket
        log.info("Attempting to delete bucket:%s" % bucket.name)
        log.debug('Gathering keys for bucket:%s' % bucket.name)
        keys = bucket.get_all_keys()
        # Only delete bucket if no keys present
        can_delete_bucket = False
        if not keys:
            log.debug('No keys in bucket, can delete')
            can_delete_bucket = True
        elif force:
            log.debug('Keys exist, but force specified, deleting keys first')
            for key in keys:
                log.debug('Deleting key:%s' % key.name)
                try:
                    bucket.delete_key(key.name)
                except s3_error, s:
                    log.error('Error deleting key:%s' % str(s))
                    return False
            can_delete_bucket = True
        if can_delete_bucket:
            log.info('Deleting bucket:%s' % bucket.name)
            self.boto.delete_bucket(bucket.name)
            return True
        return False

    def get(self, bucket_name, key_name=None, file_name=None):
        '''
        If key name given, return key contents. If file name given, write
        to that file
        If only bucket name given, return that bucket
        '''
        log.info('Checking bucket:%s exists' % bucket_name)
        try:
            bucket = self.boto.get_bucket(bucket_name)
            log.info('Bucket:%s exists' % bucket.name)
        except s3_error, s:
            log.error('Cannot find bucket:%s' % str(s))
            return None
        # If no key name, just return bucket
        if not key_name:
            return bucket

        log.info('Attempting to find key:%s in bucket:%s' % (key_name,
                                                              bucket.name))
        try:
            key = bucket.get_key(key_name)
            log.info('Key:%s found for bucket:%s' % (key.name, bucket.name))
        except s3_error, s:
            log.error('Cannot find key:%s' % str(s))
            return None
        if file_name:
            full_name = os.path.abspath(file_name)
            log.info('Writing contents of key:%s to file:%s' % (key.name,
                                                                full_name))
            with open(full_name, 'w+') as f:
                f.write(key.get_contents_as_string())
            return full_name
        log.info('Returning contents as string')
        return key.get_contents_as_string()
