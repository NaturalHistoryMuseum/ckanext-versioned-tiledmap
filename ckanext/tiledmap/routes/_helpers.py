# !/usr/bin/env python
# encoding: utf-8
#
# This file is part of ckanext-versioned-tiledmap
# Created by the Natural History Museum in London, UK

import StringIO
import base64
import gzip
import json
import urllib
from collections import defaultdict

from ckanext.tiledmap.config import config

from ckan.common import json
from ckan.lib.render import find_template
from ckan.plugins import toolkit


class MapViewSettings(object):
    '''
    Class that holds settings and functions used to build the map-info response.
    '''

    def __init__(self, fetch_id, view, resource):
        '''
        :param fetch_id: the id of the request, as provided by the javascript module. This is used
                         to keep track on the javascript side of the order map-info requests.
        :param view: the view dict
        :param resource: the resource dict
        '''
        self.fetch_id = fetch_id
        self.view = view
        self.resource = resource
        self.view_id = view[u'id']
        self.resource_id = resource[u'id']

    @property
    def title(self):
        return self.view[u'utf_grid_title']

    @property
    def fields(self):
        info_fields = list(self.view.get(u'utf_grid_fields', []))
        if self.title not in info_fields:
            info_fields.append(self.title)
        return info_fields

    @property
    def repeat_map(self):
        return bool(self.view.get(u'repeat_map', False))

    @property
    def overlapping_records_view(self):
        return self.view.get(u'overlapping_records_view', None)

    @property
    def enable_utf_grid(self):
        return bool(self.view.get(u'enable_utf_grid', False))

    @property
    def plot_map_enabled(self):
        return bool(self.view.get(u'enable_plot_map', False))

    @property
    def grid_map_enabled(self):
        return bool(self.view.get(u'enable_grid_map', False))

    @property
    def heat_map_enabled(self):
        return bool(self.view.get(u'enable_heat_map', False))

    def is_enabled(self):
        '''
        Returns True if at least one of the map styles (plot, grid, heat) is enabled. If none of
        them are, returns False.

        :return: True if one map style is enabled, False if none are
        '''
        return self.plot_map_enabled or self.grid_map_enabled or self.heat_map_enabled

    def _render_template(self, name, extra_vars):
        '''
        Render the given mustache template using the given variables. If the resource this view is
        attached to has a format then this function will attempt to find a format appropriate
        function.

        :param name: the name of the template
        :param extra_vars: a dict of variables to pass to the template renderer
        :return: a rendered template
        '''
        # this is the base name of the template, if there's no format version available then we'll
        # just return this
        template_name = u'{}.mustache'.format(name)

        resource_format = self.resource.get(u'format', None)
        # if there is a format on the resource, attempt to find a format specific template
        if resource_format is not None:
            formatted_template_name = u'{}.{}.mustache'.format(name, resource_format.lower())
            if find_template(formatted_template_name):
                template_name = formatted_template_name

        return toolkit.render(template_name, extra_vars)

    def render_info_template(self):
        '''
        Renders the point info template and returns the result.

        :return: the rendered point info template
        '''
        return self._render_template(config[u'versioned_tilemap.info_template'], {
            u'title': self.title,
            u'fields': self.fields,
            u'overlapping_records_view': self.overlapping_records_view,
            })

    def render_quick_info_template(self):
        '''
        Renders the point hover info template and returns the result.

        :return: the rendered point hover info template
        '''
        return self._render_template(config[u'versioned_tilemap.quick_info_template'], {
            u'title': self.title,
            u'fields': self.fields,
            })

    def get_style_params(self, style, names):
        '''
        Returns a dict of style params for the given style. The parameters are retrieved from the
        user defined settings on the view and if they're missing then they're retrieved from the
        config object.

        :param style: the name of the style (plot, gridded or heatmap)
        :param names: the names of the parameters to retrieve, these are also used as the names in
                      the dict that the parameter values are stored under
        :return: a dict
        '''
        params = {}
        for name in names:
            view_param_name = u'{}_{}'.format(style, name)
            config_param_name = u'versioned_tilemap.style.{}.{}'.format(style, name)
            params[name] = self.view.get(view_param_name, config[config_param_name])
        return params

    def get_extent_info(self):
        '''
        Retrieves the extent information about the datastore query provided by the parameters in the
        request. The return value is a 3-tuple containing:

            - the total number of records in the query result
            - the total number of records in the query result that have geometric data (specifically
              ones that have a value in the `meta.geo` field
            - the bounds of the query result, this is given as the top left and bottom right
              latitudinal and longitudinal values, each as a list, nested in another list
              (e.g. [[0, 4], [70, 71]]). This is how it is returned by the datastore_query_extent
              action.

        :return: a 3-tuple - (int, int, list)
        '''
        q, filters = extract_q_and_filters()
        # get query extent and counts
        extent_info = toolkit.get_action(u'datastore_query_extent')({}, {
            u'resource_id': self.resource_id,
            u'q': q,
            u'filters': filters,
            })
        # total_count and geom_count will definitely be present, bounds on the other hand is an
        # optional part of the response
        return (extent_info[u'total_count'], extent_info[u'geom_count'],
                extent_info.get(u'bounds', ((83, -170), (-83, 170))))

    def get_query_body(self):
        '''
        Returns the actual elasticsearch query dict as a base64 encoded, gzipped, JSON string. This
        will be passed to the map tile server. This may seem a bit weird to do this but it allows
        all queries to come through the same code path (and therefore trigger any datastore-search
        implementing plugins) without all map tile queries having to come through CKAN (which would
        be a performance bottle neck). The flow is like so:

            - The query is changed by the user (or indeed they arrive at the map view for the first
              time
            - /map-info is requested
            - this function builds the query, and the result is added to the /map-info response
            - the javascript on the map view receives the /map-info response and extracts the
              compressed query that was created by this function
            - the query body is then sent along with all tile requests to the tile server, which
              decompresses it and uses it to search elasticsearch

        :return: a url safe base64 encoded, gzipped, JSON string
        '''
        q, filters = extract_q_and_filters()
        result = toolkit.get_action(u'datastore_search')({}, {
            u'resource_id': self.resource_id,
            u'q': q,
            u'filters': filters,
            u'run_query': False,
            })
        out = StringIO.StringIO()
        with gzip.GzipFile(fileobj=out, mode=u'w') as f:
            json.dump(result, f)
        return base64.urlsafe_b64encode(out.getvalue())

    def create_map_info(self):
        '''
        Using the settings available on this object, create the /map-info response dict and return
        it.

        :return: a dict
        '''
        # get the standard map info dict (this provides a fresh one each time it's called)
        map_info = get_base_map_info()

        # add the base64 encoded, gzipped, JSON query
        map_info[u'query_body'] = self.get_query_body()

        # add the extent data
        total_count, geom_count, bounds = self.get_extent_info()
        map_info[u'total_count'] = total_count
        map_info[u'geom_count'] = geom_count
        map_info[u'bounds'] = bounds

        # add a few basic settings
        map_info[u'repeat_map'] = self.repeat_map
        map_info[u'fetch_id'] = self.fetch_id
        map_info[u'plugin_options'][u'tooltipInfo'] = {
            u'count_field': u'count',
            u'template': self.render_quick_info_template(),
            }
        map_info[u'plugin_options'][u'pointInfo'] = {
            u'count_field': u'count',
            u'template': self.render_info_template(),
            }

        # remove or augment the heatmap settings depending on whether it's enabled for this view
        if not self.heat_map_enabled:
            del map_info[u'map_styles'][u'heatmap']
        else:
            params = self.get_style_params(u'heatmap', [u'point_radius', u'cold_colour',
                                                        u'hot_colour', u'intensity'])
            map_info[u'map_styles'][u'heatmap'][u'tile_source'][u'params'] = params
            map_info[u'map_style'] = u'heatmap'

        # remove or augment the gridded settings depending on whether it's enabled for this view
        if not self.grid_map_enabled:
            del map_info[u'map_styles'][u'gridded']
        else:
            map_info[u'map_styles'][u'gridded'][u'has_grid'] = self.enable_utf_grid
            params = self.get_style_params(u'gridded', [u'grid_resolution', u'hot_colour',
                                                        u'cold_colour', u'range_size'])
            map_info[u'map_styles'][u'gridded'][u'tile_source'][u'params'] = params
            map_info[u'map_style'] = u'gridded'

        # remove or augment the plot settings depending on whether it's enabled for this view
        if not self.plot_map_enabled:
            del map_info[u'map_styles'][u'plot']
        else:
            map_info[u'map_styles'][u'plot'][u'has_grid'] = self.enable_utf_grid
            params = self.get_style_params(u'plot', [u'point_radius', u'point_colour',
                                                     u'border_width', u'border_colour'])
            map_info[u'map_styles'][u'plot'][u'tile_source'][u'params'] = params
            map_info[u'map_style'] = u'plot'

        return map_info

    @classmethod
    def from_request(cls):
        '''
        Setup by creating a MapViewSettings object with all the information
        needed to serve the request.
        '''
        # get the resource id from the request
        resource_id = toolkit.request.params.get(u'resource_id', None)
        view_id = toolkit.request.params.get(u'view_id', None)

        # error if the resource id is missing
        if resource_id is None:
            toolkit.abort(400, toolkit._(u'Missing resource id'))
        # error if the view id is missing
        if view_id is None:
            toolkit.abort(400, toolkit._(u'Missing view id'))

        # attempt to retrieve the resource and the view
        try:
            resource = toolkit.get_action(u'resource_show')({}, {
                u'id': resource_id
                })
        except toolkit.ObjectNotFound:
            return toolkit.abort(404, toolkit._(u'Resource not found'))
        except toolkit.NotAuthorized:
            return toolkit.abort(401, toolkit._(u'Unauthorized to read resource'))
        try:
            view = toolkit.get_action(u'resource_view_show')({}, {
                u'id': view_id
                })
        except toolkit.ObjectNotFound:
            return toolkit.abort(404, toolkit._(u'Resource view not found'))
        except toolkit.NotAuthorized:
            return toolkit.abort(401, toolkit._(u'Unauthorized to read resource view'))

        fetch_id = int(toolkit.request.params.get(u'fetch_id'))

        # create a settings object, ready for use in the map_info call
        return cls(fetch_id, view, resource)


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
    q = None if u'q' not in toolkit.request.params else urllib.unquote(toolkit.request.params[u'q'])

    # pull out the filters if there are any
    filters = defaultdict(list)
    filter_param = toolkit.request.params.get(u'filters', None)
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
                u'name': toolkit._(u'Heat Map'),
                u'icon': u'<i class="fa fa-fire"></i>',
                u'controls': [u'drawShape', u'mapType', u'fullScreen', u'miniMap'],
                u'has_grid': False,
                u'tile_source': {
                    u'url': png_url,
                    u'params': {},
                    },
                },
            u'gridded': {
                u'name': toolkit._(u'Grid Map'),
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
                u'name': toolkit._(u'Plot Map'),
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
