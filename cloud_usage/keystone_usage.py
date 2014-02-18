import argparse
from keystoneclient.v2_0 import client as key_v2

class KeystoneHelper(object):
    def __init__(self, admin_password, auth_url):
        self.keystone = key_v2.Client(username='admin',
                                      password=admin_password,
                                      tenant_name='admin',
                                      auth_url=auth_url)

    def keystone_usage(self):
        return { 'tenant-count' : len(self.keystone.tenants.list()),
                 'user-count' : len(self.keystone.users.list()) }

    def print_usage(self):
        usage = self.keystone_usage()
        print '---------------'
        print 'Keystone Usage'
        print '--------------'
        for key, value in usage.iteritems():
            print key, ':', value

def parse_args():
    a = argparse.ArgumentParser(description='Get cinder usage')
    a.add_argument('admin_password', help='Auth admin password')
    a.add_argument('auth_url', help='Auth url')
    return a.parse_args()

def main():
    args = parse_args()
    kh = KeystoneHelper(args.admin_password, args.auth_url)
    kh.print_usage()

if __name__ == '__main__':
    main()
