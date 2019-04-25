#!/usr/bin/env python
# encoding: utf-8
#
# This file is part of a project
# Created by the Natural History Museum in London, UK

import urllib
from collections import defaultdict

from pylons import request

from ckan.common import _
from ckanext.tiledmap.config import config


def build_url(*parts):
    '''
    Given a bunch of parts, build a URL by joining them together with a /.

    :param parts: the URL parts
    :return: a URL string
    '''
    return u'/'.join(part.strip(u'/') for part in parts)


def extract_q_and_filters():
    '''
    Extract the q and filters query string parameters from the request. These are standard
    parameters in the resource views and have a standardised format too.

    :return: a 2-tuple of the q value (string, or None) and the filters value (dict, or None)
    '''
    # get the query if there is one
    q = None if u'q' not in request.params else urllib.unquote(request.params[u'q'])

    # pull out the filters if there are any
    filters = defaultdict(list)
    filter_param = request.params.get(u'filters', None)
    if filter_param:
        for field_and_value in urllib.unquote(filter_param).split(u'|'):
            if u':' in field_and_value:
                field, value = field_and_value.split(u':', 1)
                filters[field].append(value)

    return q, filters


def get_base_map_info():
    '''
    Creates the base map info dict of settings. All of the settings in this dict are static in that
    they will be the same for all map views created on the currently running CKAN instance (they use
    either always static values or ones that are pulled from the config which can are set on boot).

    A few settings are missing, these are set in MapViewSettings.create_map_info as they require
    custom per-map settings that the user has control over or are dependant on the target resource.

    :return: a dict of settings
    '''
    png_url = build_url(config[u'versioned_tilemap.tile_server'], u'/{z}/{x}/{y}.png')
    utf_grid_url = build_url(config[u'versioned_tilemap.tile_server'], u'/{z}/{x}/{y}.grid.json')

    return {
        u'geospatial': True,
        u'zoom_bounds': {
            u'min': int(config[u'versioned_tilemap.zoom_bounds.min']),
            u'max': int(config[u'versioned_tilemap.zoom_bounds.max']),
        },
        u'initial_zoom': {
            u'min': int(config[u'versioned_tilemap.initial_zoom.min']),
            u'max': int(config[u'versioned_tilemap.initial_zoom.max']),
        },
        u'tile_layer': {
            u'url': config[u'versioned_tilemap.tile_layer.url'],
            u'opacity': float(config[u'versioned_tilemap.tile_layer.opacity'])
        },
        u'control_options': {
            u'fullScreen': {
                u'position': u'topright'
            },
            u'drawShape': {
                u'draw': {
                    u'polyline': False,
                    u'marker': False,
                    u'circle': False,
                    u'country': True,
                    u'polygon': {
                        u'allowIntersection': False,
                        u'shapeOptions': {
                            u'stroke': True,
                            u'colour': u'#FF4444',
                            u'weight': 5,
                            u'opacity': 0.5,
                            u'fill': True,
                            u'fillcolour': u'#FF4444',
                            u'fillOpacity': 0.1
                        }
                    }
                },
                u'position': u'topleft'
            },
            u'selectCountry': {
                u'draw': {
                    u'fill': u'#FF4444',
                    u'fill-opacity': 0.1,
                    u'stroke': u'#FF4444',
                    u'stroke-opacity': 0.5
                }
            },
            u'mapType': {
                u'position': u'bottomleft'
            },
            u'miniMap': {
                u'position': u'bottomright',
                u'tile_layer': {
                    u'url': config[u'versioned_tilemap.tile_layer.url']
                },
                u'zoomLevelFixed': 1,
                u'toggleDisplay': True,
                u'viewport': {
                    u'marker_zoom': 8,
                    u'rect': {
                        u'weight': 1,
                        u'colour': u'#0000FF',
                        u'opacity': 1,
                        u'fill': False
                    },
                    u'marker': {
                        u'weight': 1,
                        u'colour': u'#0000FF',
                        u'opacity': 1,
                        u'radius': 3,
                        u'fillcolour': u'#0000FF',
                        u'fillOpacity': 0.2
                    }
                }
            }
        },
        u'plugin_options': {
            u'tooltipCount': {
                u'count_field': u'count'
            },
        },
        u'map_styles': {
            u'heatmap': {
                u'name': _(u'Heat Map'),
                u'icon': u'<i class="fa fa-fire"></i>',
                u'controls': [u'drawShape', u'mapType', u'fullScreen', u'miniMap'],
                u'has_grid': False,
                u'tile_source': {
                    u'url': png_url,
                    u'params': {},
                },
            },
            u'gridded': {
                u'name': _(u'Grid Map'),
                u'icon': u'<i class="fa fa-th"></i>',
                u'controls': [u'drawShape', u'mapType', u'fullScreen', u'miniMap'],
                u'plugins': [u'tooltipCount'],
                u'grid_resolution': int(config[u'versioned_tilemap.style.gridded.grid_resolution']),
                u'tile_source': {
                    u'url': png_url,
                    u'params': {},
                },
                u'grid_source': {
                    u'url': utf_grid_url,
                    u'params': {},
                },
            },
            u'plot': {
                u'name': _(u'Plot Map'),
                u'icon': u'<i class="fa fa-dot-circle-o"></i>',
                u'controls': [u'drawShape', u'mapType', u'fullScreen', u'miniMap'],
                u'plugins': [u'tooltipInfo', u'pointInfo'],
                u'grid_resolution': int(config[u'versioned_tilemap.style.plot.grid_resolution']),
                u'tile_source': {
                    u'url': png_url,
                    u'params': {},
                },
                u'grid_source': {
                    u'url': utf_grid_url,
                    u'params': {},
                },
            },
        },
    }
