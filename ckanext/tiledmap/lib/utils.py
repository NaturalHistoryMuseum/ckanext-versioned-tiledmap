#!/usr/bin/env python
# encoding: utf-8
#
# This file is part of a project
# Created by the Natural History Museum in London, UK

from ckan.plugins import toolkit


def get_resource_datastore_fields(resource_id):
    data = {'resource_id': resource_id, 'limit': 0}
    all_fields = toolkit.get_action('datastore_search')({}, data)['fields']
    return set(field['id'] for field in all_fields)
