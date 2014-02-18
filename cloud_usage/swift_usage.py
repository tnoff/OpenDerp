import argparse
from contextlib import contextmanager
from keystoneclient.v2_0 import client as key_v2
import random
import string
import swiftclient

class SwiftHelper(object):
    def __init__(self, admin_password, auth_url):
        self.auth_url = auth_url
        self.keystone = key_v2.Client(username='admin',
                                      password=admin_password,
                                      tenant_name='admin',
                                      auth_url=auth_url)

    def __random(self, size=10, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

    @contextmanager
    def __temp_user(self, username, password):
        user = self.keystone.users.create(username, password, None)
        try:
            yield user
        finally:
            self.keystone.users.delete(user)

    def __get_member_role(self):
        roles = self.keystone.roles.list()
        for r in roles:
            if 'member' in r.name.lower():
                return r
        return None

    def swift_usage(self):
        usage_dict = {'containers' : 0,
                      'bytes_used' : 0,
                      'megabytes_used' : 0}
        username = self.__random()
        password = self.__random()
        with self.__temp_user(username, password) as user:
            tenant_list = self.keystone.tenants.list()
            member = self.__get_member_role()
            for tenant in tenant_list:
                self.keystone.tenants.add_user(tenant.id, user.id, member.id)
                swift = swiftclient.client.Connection(auth_version='2', user=user.name, key=password, tenant_name=tenant.name, authurl=self.auth_url)
                info = swift.head_account()
                usage_dict['containers'] += int(info['x-account-container-count'])
                usage_dict['bytes_used'] += int(info['x-account-bytes-used'])
                usage_dict['megabytes_used'] += int(info['x-account-bytes-used']) / (1024 * 1024.0)
        return usage_dict

    def print_usage(self):
        usage = self.swift_usage()
        print '-----------------'
        print 'Swift Usage'
        print '-----------'
        for key, value in usage.iteritems():
            print key, ':', value

def parse_args():
    a = argparse.ArgumentParser(description='Get cluster object storage usage')
    a.add_argument('admin_password', help='Auth password')
    a.add_argument('auth_url', help='Keystone auth url')
    return a.parse_args()

def main():
    args = parse_args()
    sh = SwiftHelper(args.admin_password, args.auth_url)
    sh.print_usage()

if __name__ == '__main__':
    main()
