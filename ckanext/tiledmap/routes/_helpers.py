# !/usr/bin/env python
# encoding: utf-8
#
# This file is part of ckanext-versioned-tiledmap
# Created by the Natural History Museum in London, UK

import base64
import gzip
import json
from collections import defaultdict
from urllib.parse import unquote

from ckan.common import json
from ckan.plugins import toolkit
from ckanext.tiledmap.config import config


class MapViewSettings:
    """
    Class that holds settings and functions used to build the map-info response.
    """

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
        self.view_id = view['id']
        self.resource_id = resource['id']

    @property
    def title(self):
        return self.view['utf_grid_title']

    @property
    def fields(self):
        info_fields = list(self.view.get('utf_grid_fields', []))
        if self.title not in info_fields:
            info_fields.append(self.title)
        return info_fields

    @property
    def repeat_map(self):
        return bool(self.view.get('repeat_map', False))

    @property
    def overlapping_records_view(self):
        return self.view.get('overlapping_records_view', None)

    @property
    def enable_utf_grid(self):
        return bool(self.view.get('enable_utf_grid', False))

    @property
    def plot_map_enabled(self):
        return bool(self.view.get('enable_plot_map', False))

    @property
    def grid_map_enabled(self):
        return bool(self.view.get('enable_grid_map', False))

    @property
    def heat_map_enabled(self):
        return bool(self.view.get('enable_heat_map', False))

    def is_enabled(self):
        """
        Returns True if at least one of the map styles (plot, grid, heat) is enabled. If
        none of them are, returns False.

        :return: True if one map style is enabled, False if none are
        """
        return self.plot_map_enabled or self.grid_map_enabled or self.heat_map_enabled

    def _render_template(self, name, extra_vars):
        """
        Render the given mustache template using the given variables. If the resource
        this view is attached to has a format then this function will attempt to find a
        format appropriate function.

        :param name: the name of the template
        :param extra_vars: a dict of variables to pass to the template renderer
        :return: a rendered template
        """
        # this is the base name of the template, if there's no format version available then we'll
        # just return this
        template_name = f'{name}.mustache'

        resource_format = self.resource.get('format', None)
        # if there is a format on the resource, attempt to find a format specific template
        if resource_format is not None:
            formatted_template_name = f'{name}.{resource_format.lower()}.mustache'
            paths = config['computed_template_paths']
            if any(path for path in paths if path.endswith(formatted_template_name)):
                template_name = formatted_template_name

        return toolkit.render(template_name, extra_vars)

    def render_info_template(self):
        """
        Renders the point info template and returns the result.

        :return: the rendered point info template
        """
        return self._render_template(
            config['versioned_tilemap.info_template'],
            {
                'title': self.title,
                'fields': self.fields,
                'overlapping_records_view': self.overlapping_records_view,
            },
        )

    def render_quick_info_template(self):
        """
        Renders the point hover info template and returns the result.

        :return: the rendered point hover info template
        """
        return self._render_template(
            config['versioned_tilemap.quick_info_template'],
            {
                'title': self.title,
                'fields': self.fields,
            },
        )

    def get_style_params(self, style, names):
        """
        Returns a dict of style params for the given style. The parameters are retrieved
        from the user defined settings on the view and if they're missing then they're
        retrieved from the config object.

        :param style: the name of the style (plot, gridded or heatmap)
        :param names: the names of the parameters to retrieve, these are also used as the names in
                      the dict that the parameter values are stored under
        :return: a dict
        """
        params = {}
        for name in names:
            view_param_name = f'{style}_{name}'
            config_param_name = f'versioned_tilemap.style.{style}.{name}'
            params[name] = self.view.get(view_param_name, config[config_param_name])
        return params

    def get_extent_info(self):
        """
        Retrieves the extent information about the datastore query provided by the
        parameters in the request. The return value is a 3-tuple containing:

            - the total number of records in the query result
            - the total number of records in the query result that have geometric data (specifically
              ones that have a value in the `meta.geo` field
            - the bounds of the query result, this is given as the top left and bottom right
              latitudinal and longitudinal values, each as a list, nested in another list
              (e.g. [[0, 4], [70, 71]]). This is how it is returned by the datastore_query_extent
              action.

        :return: a 3-tuple - (int, int, list)
        """
        q, filters = extract_q_and_filters()
        # get query extent and counts
        extent_info = toolkit.get_action('datastore_query_extent')(
            {},
            {
                'resource_id': self.resource_id,
                'q': q,
                'filters': filters,
            },
        )
        # total_count and geom_count will definitely be present, bounds on the other hand is an
        # optional part of the response
        return (
            extent_info['total_count'],
            extent_info['geom_count'],
            extent_info.get('bounds', ((83, -170), (-83, 170))),
        )

    def get_query_body(self):
        """
        Returns the actual elasticsearch query dict as a base64 encoded, gzipped, JSON
        string. This will be passed to the map tile server. This may seem a bit weird to
        do this but it allows all queries to come through the same code path (and
        therefore trigger any datastore-search implementing plugins) without all map
        tile queries having to come through CKAN (which would be a performance bottle
        neck). The flow is like so:

            - The query is changed by the user (or indeed they arrive at the map view for the first
              time
            - /map-info is requested
            - this function builds the query, and the result is added to the /map-info response
            - the javascript on the map view receives the /map-info response and extracts the
              compressed query that was created by this function
            - the query body is then sent along with all tile requests to the tile server, which
              decompresses it and uses it to search elasticsearch

        :return: a url safe base64 encoded, gzipped, JSON string
        """
        q, filters = extract_q_and_filters()
        result = toolkit.get_action('datastore_search')(
            {},
            {
                'resource_id': self.resource_id,
                'q': q,
                'filters': filters,
                'run_query': False,
            },
        )
        return base64.urlsafe_b64encode(
            gzip.compress(json.dumps(result).encode('utf-8'))
        )

    def create_map_info(self):
        """
        Using the settings available on this object, create the /map-info response dict
        and return it.

        :return: a dict
        """
        # get the standard map info dict (this provides a fresh one each time it's called)
        map_info = get_base_map_info()

        # add the base64 encoded, gzipped, JSON query
        map_info['query_body'] = self.get_query_body()

        # add the extent data
        total_count, geom_count, bounds = self.get_extent_info()
        map_info['total_count'] = total_count
        map_info['geom_count'] = geom_count
        map_info['bounds'] = bounds

        # add a few basic settings
        map_info['repeat_map'] = self.repeat_map
        map_info['fetch_id'] = self.fetch_id
        map_info['plugin_options']['tooltipInfo'] = {
            'count_field': 'count',
            'template': self.render_quick_info_template(),
        }
        map_info['plugin_options']['pointInfo'] = {
            'count_field': 'count',
            'template': self.render_info_template(),
        }

        # remove or augment the heatmap settings depending on whether it's enabled for this view
        if not self.heat_map_enabled:
            del map_info['map_styles']['heatmap']
        else:
            params = self.get_style_params(
                'heatmap', ['point_radius', 'cold_colour', 'hot_colour', 'intensity']
            )
            map_info['map_styles']['heatmap']['tile_source']['params'] = params
            map_info['map_style'] = 'heatmap'

        # remove or augment the gridded settings depending on whether it's enabled for this view
        if not self.grid_map_enabled:
            del map_info['map_styles']['gridded']
        else:
            map_info['map_styles']['gridded']['has_grid'] = self.enable_utf_grid
            params = self.get_style_params(
                'gridded',
                ['grid_resolution', 'hot_colour', 'cold_colour', 'range_size'],
            )
            map_info['map_styles']['gridded']['tile_source']['params'] = params
            map_info['map_style'] = 'gridded'

        # remove or augment the plot settings depending on whether it's enabled for this view
        if not self.plot_map_enabled:
            del map_info['map_styles']['plot']
        else:
            map_info['map_styles']['plot']['has_grid'] = self.enable_utf_grid
            params = self.get_style_params(
                'plot',
                ['point_radius', 'point_colour', 'border_width', 'border_colour'],
            )
            map_info['map_styles']['plot']['tile_source']['params'] = params
            map_info['map_style'] = 'plot'

        return map_info

    @classmethod
    def from_request(cls):
        """
        Setup by creating a MapViewSettings object with all the information needed to
        serve the request.
        """
        # get the resource id from the request
        resource_id = toolkit.request.params.get('resource_id', None)
        view_id = toolkit.request.params.get('view_id', None)

        # error if the resource id is missing
        if resource_id is None:
            toolkit.abort(400, toolkit._('Missing resource id'))
        # error if the view id is missing
        if view_id is None:
            toolkit.abort(400, toolkit._('Missing view id'))

        # attempt to retrieve the resource and the view
        try:
            resource = toolkit.get_action('resource_show')({}, {'id': resource_id})
        except toolkit.ObjectNotFound:
            return toolkit.abort(404, toolkit._('Resource not found'))
        except toolkit.NotAuthorized:
            return toolkit.abort(401, toolkit._('Unauthorized to read resource'))
        try:
            view = toolkit.get_action('resource_view_show')({}, {'id': view_id})
        except toolkit.ObjectNotFound:
            return toolkit.abort(404, toolkit._('Resource view not found'))
        except toolkit.NotAuthorized:
            return toolkit.abort(401, toolkit._('Unauthorized to read resource view'))

        fetch_id = int(toolkit.request.params.get('fetch_id'))

        # create a settings object, ready for use in the map_info call
        return cls(fetch_id, view, resource)


def build_url(*parts):
    """
    Given a bunch of parts, build a URL by joining them together with a /.

    :param parts: the URL parts
    :return: a URL string
    """
    return '/'.join(part.strip('/') for part in parts)


def extract_q_and_filters():
    """
    Extract the q and filters query string parameters from the request. These are
    standard parameters in the resource views and have a standardised format too.

    :return: a 2-tuple of the q value (string, or None) and the filters value (dict, or None)
    """
    # get the query if there is one
    q = (
        None
        if 'q' not in toolkit.request.params
        else unquote(toolkit.request.params['q'])
    )

    # pull out the filters if there are any
    filter_param = toolkit.request.params.get('filters', None)
    if filter_param:
        filters = defaultdict(list)
        for field_and_value in unquote(filter_param).split('|'):
            if ':' in field_and_value:
                field, value = field_and_value.split(':', 1)
                filters[field].append(value)
    else:
        filters = None

    return q, filters


def get_base_map_info():
    """
    Creates the base map info dict of settings. All of the settings in this dict are
    static in that they will be the same for all map views created on the currently
    running CKAN instance (they use either always static values or ones that are pulled
    from the config which can are set on boot).

    A few settings are missing, these are set in MapViewSettings.create_map_info as they require
    custom per-map settings that the user has control over or are dependant on the target resource.

    :return: a dict of settings
    """
    png_url = build_url(config['versioned_tilemap.tile_server'], '/{z}/{x}/{y}.png')
    utf_grid_url = build_url(
        config['versioned_tilemap.tile_server'], '/{z}/{x}/{y}.grid.json'
    )

    return {
        'geospatial': True,
        'zoom_bounds': {
            'min': int(config['versioned_tilemap.zoom_bounds.min']),
            'max': int(config['versioned_tilemap.zoom_bounds.max']),
        },
        'initial_zoom': {
            'min': int(config['versioned_tilemap.initial_zoom.min']),
            'max': int(config['versioned_tilemap.initial_zoom.max']),
        },
        'tile_layer': {
            'url': config['versioned_tilemap.tile_layer.url'],
            'attribution': config.get('versioned_tilemap.tile_layer.attribution'),
            'opacity': float(config['versioned_tilemap.tile_layer.opacity']),
        },
        'control_options': {
            'fullScreen': {'position': 'topright'},
            'drawShape': {
                'draw': {
                    'polyline': False,
                    'marker': False,
                    'circle': False,
                    'country': True,
                    'polygon': {
                        'allowIntersection': False,
                        'shapeOptions': {
                            'stroke': True,
                            'colour': '#FF4444',
                            'weight': 5,
                            'opacity': 0.5,
                            'fill': True,
                            'fillcolour': '#FF4444',
                            'fillOpacity': 0.1,
                        },
                    },
                },
                'position': 'topleft',
            },
            'selectCountry': {
                'draw': {
                    'fill': '#FF4444',
                    'fill-opacity': 0.1,
                    'stroke': '#FF4444',
                    'stroke-opacity': 0.5,
                }
            },
            'mapType': {'position': 'bottomleft'},
            'miniMap': {
                'position': 'bottomright',
                'tile_layer': {'url': config['versioned_tilemap.tile_layer.url']},
                'zoomLevelFixed': 1,
                'toggleDisplay': True,
                'viewport': {
                    'marker_zoom': 8,
                    'rect': {
                        'weight': 1,
                        'colour': '#0000FF',
                        'opacity': 1,
                        'fill': False,
                    },
                    'marker': {
                        'weight': 1,
                        'colour': '#0000FF',
                        'opacity': 1,
                        'radius': 3,
                        'fillcolour': '#0000FF',
                        'fillOpacity': 0.2,
                    },
                },
            },
        },
        'plugin_options': {
            'tooltipCount': {'count_field': 'count'},
        },
        'map_styles': {
            'heatmap': {
                'name': toolkit._('Heat Map'),
                'icon': '<i class="fa fa-fire"></i>',
                'controls': ['drawShape', 'mapType', 'fullScreen', 'miniMap'],
                'has_grid': False,
                'tile_source': {
                    'url': png_url,
                    'params': {},
                },
            },
            'gridded': {
                'name': toolkit._('Grid Map'),
                'icon': '<i class="fa fa-th"></i>',
                'controls': ['drawShape', 'mapType', 'fullScreen', 'miniMap'],
                'plugins': ['tooltipCount'],
                'grid_resolution': int(
                    config['versioned_tilemap.style.gridded.grid_resolution']
                ),
                'tile_source': {
                    'url': png_url,
                    'params': {},
                },
                'grid_source': {
                    'url': utf_grid_url,
                    'params': {},
                },
            },
            'plot': {
                'name': toolkit._('Plot Map'),
                'icon': '<i class="fa fa-dot-circle-o"></i>',
                'controls': ['drawShape', 'mapType', 'fullScreen', 'miniMap'],
                'plugins': ['tooltipInfo', 'pointInfo'],
                'grid_resolution': int(
                    config['versioned_tilemap.style.plot.grid_resolution']
                ),
                'tile_source': {
                    'url': png_url,
                    'params': {},
                },
                'grid_source': {
                    'url': utf_grid_url,
                    'params': {},
                },
            },
        },
    }
