#!/usr/bin/env python
# encoding: utf-8

import collectd
from novaclient.v1_1 import client

VERBOSE_LOGGING = False

OS_AUTH_URL = ""
OS_PASSWORD = ""
OS_USERNAME = ""
OS_TENANT_ID = ""


def memoize(f):
    cache = {}

    def wrapper(x):
        if x not in cache:
            cache[x] = f(x)
        return cache[x]
    return wrapper


def fetch_usage(client):
    def resolve_vcpus(flavor):
        return client.flavors.get(flavor).vcpus

    vcpus = memoize(resolve_vcpus)

    def format_server(x):
        d = x.to_dict()
        result = {}
        result['host'] = d['OS-EXT-SRV-ATTR:host']
        result['flavor'] = d['flavor']['id']
        result['vcpus'] = vcpus(d['flavor']['id'])
        result['name'] = d['name']
        result['iid'] = d['id']
        return result

    return [format_server(x) for x in client.servers.list(search_opts={"all_tenants": 1})]


def log_verbose(msg):
    if not VERBOSE_LOGGING:
        return
    collectd.info('nova_cores plugin [verbose]: %s' % msg)


def dispatch_value(key, value, type):
    log_verbose('Sending value: %s=%s' % (key, value))
    val = collectd.Values(plugin='openstack_core_reservation')
    val.type = type
    val.type_instance = key
    val.values = [value]
    val.dispatch()


def read_callback():
    log_verbose('Read callback called')
    osc = client.Client(OS_USERNAME, OS_PASSWORD, OS_TENANT_ID, OS_AUTH_URL)
    servers = fetch_usage(osc)
    total_vcpus = sum(server['vcpus'] for server in servers)
    log_verbose("total vcpu usage: %s" % total_vcpus)
    dispatch_value("openstack_core_reservation", total_vcpus, "gauge")
    log_verbose("value dispatched")


def configure_callback(conf):
    global VERBOSE_LOGGING, OS_AUTH_URL, OS_USERNAME, OS_PASSWORD, OS_TENANT_ID
    for node in conf.children:
        if node.key == 'Verbose':
            VERBOSE_LOGGING = bool(node.values[0])
        elif node.key == 'AuthURL':
            OS_AUTH_URL = node.values[0]
        elif node.key == 'User':
            OS_USERNAME = node.values[0]
        elif node.key == 'Password':
            OS_PASSWORD = node.values[0]
        elif node.key == 'TenantID':
            OS_TENANT_ID = node.values[0]

collectd.register_config(configure_callback)
collectd.register_read(read_callback)
