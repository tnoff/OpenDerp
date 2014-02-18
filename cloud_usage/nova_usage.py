import argparse
from novaclient.v1_1 import client as nova_v1

FLAVOR_KEYS = ['ram', 'vcpus', 'swap', 'disk', 'OS-FLV-EXT-DATA:ephemeral']

class NovaHelper(object):
    def __init__(self, admin_password, auth_url):
        self.nova = nova_v1.Client('admin', admin_password,
                                   'admin', auth_url)

    def __list_to_dict(self, list_obj, key='id'):
        d = dict()
        for item in list_obj:
            args = vars(item)['_info']
            obj_id = args.pop(key)
            d[obj_id] = args
        return d

    def instance_by_tenant(self):
        instances = self.nova.servers.list(search_opts={'all_tenants' : 1 })
        tenant_servers = {}
        for instance in instances:
            tenant_servers.setdefault(instance.tenant_id, [])
            tenant_servers[instance.tenant_id].append(instance)
        return tenant_servers

    def instance_usage(self, instance_list, flavors=None):
        flavors = flavors or self.__list_to_dict(self.nova.flavors.list())
        usage_dict = dict()
        for key in FLAVOR_KEYS:
            usage_dict[key] = 0
        instance_count = 0
        for instance in instance_list:
            instance_count += 1
            instance_flavor = flavors[instance.flavor['id']]
            if instance_flavor['swap'] == '':
                instance_flavor['swap'] = 0
            for key in FLAVOR_KEYS:
                usage_dict[key] += float(instance_flavor[key])
        usage_dict['instance-count'] = instance_count
        return usage_dict

    def print_usage(self):
        instances = self.instance_by_tenant()
        flavors = self.__list_to_dict(self.nova.flavors.list())
        usage_totals = dict()
        for key in FLAVOR_KEYS:
            usage_totals[key] = 0
        usage_totals['instance-count'] = 0
        for tenant, instance_list in instances.iteritems():
            usage = self.instance_usage(instance_list, flavors=flavors)
            print 'Tenant:', tenant
            print '---------------'
            print 'Nova Usage'
            for key, value in usage.iteritems():
                print key, ':', value
                usage_totals[key] += value
            print '----------------'
        print 'Cluster Nova Totals'
        print '------------------'
        for key, value in usage_totals.iteritems():
            print key, ':', value

def parse_args():
    a = argparse.ArgumentParser(description='Get total nova usage')
    a.add_argument('admin_password', help='Auth admin password')
    a.add_argument('auth_url', help='Auth url')
    return a.parse_args()

def main():
    args = parse_args()
    nh = NovaHelper(args.admin_password, args.auth_url)
    nh.print_usage()

if __name__ == '__main__':
    main()
