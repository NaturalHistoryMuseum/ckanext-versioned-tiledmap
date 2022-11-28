# !/usr/bin/env python
# encoding: utf-8
#
# This file is part of ckanext-versioned-tiledmap
# Created by the Natural History Museum in London, UK

from flask import Blueprint, jsonify

from . import _helpers

blueprint = Blueprint(name='map', import_name=__name__, url_prefix='')


@blueprint.route('/map-info')
def info():
    """
    Returns metadata about a given map in JSON form.

    :return: A JSON encoded string representing the metadata
    """
    view_settings = _helpers.MapViewSettings.from_request()

    # ensure we have at least one map style enabled
    if not view_settings.is_enabled():
        return jsonify({'geospatial': False})

    return jsonify(view_settings.create_map_info())
