import argparse
from cinder_usage import CinderHelper
from glance_usage import GlanceHelper
from keystone_usage import KeystoneHelper
from nova_usage import NovaHelper
from swift_usage import SwiftHelper

class CloudHelper(object):
    def __init__(self, admin_password, auth_url):
        self.cinder = CinderHelper(admin_password, auth_url)
        self.glance = GlanceHelper(admin_password, auth_url)
        self.keystone = KeystoneHelper(admin_password, auth_url)
        self.nova = NovaHelper(admin_password, auth_url)
        self.swift = SwiftHelper(admin_password, auth_url)

    def print_usage(self):
        self.cinder.print_usage()
        self.glance.print_usage()
        self.keystone.print_usage()
        self.nova.print_usage()
        self.swift.print_usage()

def parse_args():
    a = argparse.ArgumentParser(description='Get cinder usage')
    a.add_argument('admin_password', help='Auth admin password')
    a.add_argument('auth_url', help='Auth url')
    return a.parse_args()

def main():
    args = parse_args()
    ch = CloudHelper(args.admin_password, args.auth_url)
    ch.print_usage()

if __name__ == '__main__':
    main()
