#!/usr/bin/env python
# encoding: utf-8
#
# This file is part of a project
# Created by the Natural History Museum in London, UK

from ckan.plugins import toolkit
import urllib.request
from cachetools import cached, TTLCache


def get_resource_datastore_fields(resource_id):
    data = {'resource_id': resource_id, 'limit': 0}
    all_fields = toolkit.get_action('datastore_search')({}, data)['fields']
    return set(field['id'] for field in all_fields)


@cached(cache=TTLCache(maxsize=10, ttl=300))
def get_tileserver_status():
    tileserver_url = toolkit.config.get('versioned_tilemap.tile_server')

    tileserver_response_text = 'unknown'

    if tileserver_url:
        try:
            with urllib.request.urlopen(tileserver_url + '/status') as response:
                tileserver_response = response.read().decode()
        except Exception as e:
            tileserver_response = ''
        if tileserver_response == 'OK':
            tileserver_response_text = 'available'
        else:
            tileserver_response_text = 'unavailable'

    return tileserver_response_text