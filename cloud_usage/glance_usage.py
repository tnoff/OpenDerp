import argparse
from glanceclient import Client as glance_client
from keystoneclient.v2_0 import client as key_v2
from novaclient.v1_1 import client as nova_v1

class GlanceHelper(object):
    def __init__(self, admin_password, auth_url):
        self.nova = nova_v1.Client('admin', admin_password, 'admin', auth_url)
        self.keystone = key_v2.Client(username='admin',
                                      password=admin_password,
                                      tenant_name='admin',
                                      auth_url=auth_url)

        token, image_endpoint = self.__setup_glance()
        self.glance = glance_client('1', endpoint=image_endpoint, token=token)

    def __setup_glance(self):
        token = self.keystone.auth_token
        service_catalog = self.keystone.service_catalog
        catalog = service_catalog.catalog['serviceCatalog']
        glance_ip = None
        for endpoint in catalog:
            if 'image' == endpoint['type']:
                glance_ip = endpoint['endpoints'][0]['publicURL']
        return token, glance_ip

    def image_usage(self):
        image_list = self.nova.images.list()
        disk_format_usage = dict()
        for image in image_list:
            glance_image = self.glance.images.get(image.id)
            args = vars(glance_image)['_info']
            disk_format_usage.setdefault(args['disk_format'], {'total-count' : 0, 'total-size' : 0 })
            disk_format_usage[args['disk_format']]['total-count'] += 1
            disk_format_usage[args['disk_format']]['total-size'] += args['size']
        return disk_format_usage

    def print_usage(self):
        usage = self.image_usage()
        print '----------------'
        print 'Image Usage Data'
        total_images = 0
        total_size = 0
        for image_type, image_data in usage.iteritems():
            print '----------------'
            print 'Disk format type:', image_type
            print 'Image Count:', image_data['total-count']
            print 'Total Size:', image_data['total-size'] / ( 1024 * 1024.0), 'MB'
            total_images += image_data['total-count']
            total_size += image_data['total-size']
        print '----------------'
        print 'Total Image Data'
        print 'Image Count:', total_images
        print 'Total Size:', total_size / ( 1024 * 1024.0), 'MB'

def parse_args():
    a = argparse.ArgumentParser(description='Get cinder usage')
    a.add_argument('admin_password', help='Auth admin password')
    a.add_argument('auth_url', help='Auth url')
    return a.parse_args()

def main():
    args = parse_args()
    gh = GlanceHelper(args.admin_password, args.auth_url)
    gh.print_usage()

if __name__ == '__main__':
    main()
