#!/usr/bin/env python
# encoding: utf-8
#
# This file is part of a project
# Created by the Natural History Museum in London, UK

from ckan import plugins


def get_resource_datastore_fields(resource_id):
    data = {u'resource_id': resource_id, u'limit': 0}
    all_fields = plugins.toolkit.get_action(u'datastore_search')({}, data)[u'fields']
    return set(field[u'id'] for field in all_fields)
