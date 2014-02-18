import argparse
from cinderclient.v1 import client as cinder_v1

class CinderHelper(object):
    def __init__(self, admin_password, auth_url):
        self.cinder = cinder_v1.Client('admin', admin_password, 'admin', auth_url)

    def volume_usage(self):
        volume_usage = dict()
        for volume in self.cinder.volumes.list({'all_tenants' : 1}):
            args = vars(volume)['_info']
            volume_usage.setdefault(args['volume_type'], {'total_number' : 0, 'total_size' : 0})
            volume_usage[args['volume_type']]['total_number'] += 1
            volume_usage[args['volume_type']]['total_size'] += args['size']
        return volume_usage

    def print_usage(self):
        usage = self.volume_usage()
        print '---------------'
        print 'Volumes By Type'
        total_number = 0
        total_size = 0
        for vol_type, vol_data in usage.iteritems():
            print '---------------'
            print 'Volume Type:', vol_type
            print 'Volume Count', vol_data['total_number']
            print 'Volume Size', vol_data['total_size']
            total_number += vol_data['total_number']
            total_size += vol_data['total_size']
        print '---------------'
        print 'Volume Totals'
        print 'Total Count:', total_number
        print 'Total Size:', total_size

def parse_args():
    a = argparse.ArgumentParser(description='Get cinder usage')
    a.add_argument('admin_password', help='Auth admin password')
    a.add_argument('auth_url', help='Auth url')
    return a.parse_args()

def main():
    args = parse_args()
    ch = CinderHelper(args.admin_password, args.auth_url)
    ch.print_usage()

if __name__ == '__main__':
    main()
