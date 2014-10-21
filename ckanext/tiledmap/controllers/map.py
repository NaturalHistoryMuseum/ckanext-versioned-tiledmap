import urllib

from ckan import plugins
from ckan.plugins import toolkit

from ckan.common import json, request, response, _
from ckan.lib.render import find_template

from ckanext.tiledmap.db import _get_engine
from ckanext.tiledmap.config import config

from ckanext.datastore import db as datastore_db
from ckanext.datastore import interfaces
from ckanext.datastore.helpers import is_single_statement


class MapController(toolkit.BaseController):
    """Controller for getting map setting and information.

    This is implemented as a controller (rather than providing the data directly
    to the javascript module) because the map will generate new queries without
    page reloads.

    The map setting and information is available at `/map-info`.
    This request expects a 'resource_id' parameter, and accepts `filters` and
    `q` formatted as per resource view URLs.

    See ckanext.tiledmap.config for configuration options.
    """

    def __before__(self, action, **params):
        """Setup the request

        This will trigger a 400 error if the resource_id parameter is missing.
        """
        # Run super
        super(MapController, self).__before__(action, **params)

        # Setup fields names
        self.geom_field = config['tiledmap.geom_field']
        self.geom_field_4326 = config['tiledmap.geom_field_4326']

        # Get request resource_id
        if not request.params.get('resource_id'):
            toolkit.abort(400, _("Missing resource id"))

        self.resource_id = request.params.get('resource_id')

        try:
            resource_show = toolkit.get_action('resource_show')
            self.resource = resource_show(None, {'id': self.resource_id})
        except toolkit.NotFound:
            toolkit.abort(404, _('Resource not found'))
        except toolkit.NotAuthorized:
            toolkit.abort(401, _('Unauthorized to read resources'))
        resource_view_show = toolkit.get_action('resource_view_show')
        self.view_id = request.params.get('view_id')
        self.view = resource_view_show(None, {'id': self.view_id})

        # Read resource-dependent parameters
        self.info_title = self.view['utf_grid_title']
        try:
            self.info_fields = self.view['utf_grid_fields']
        except KeyError:
            self.info_fields = []
        self.info_template = config['tiledmap.info_template']
        self.quick_info_template = config['tiledmap.quick_info_template']
        self.repeat_map = self.view['repeat_map']

        # Fields that need to be added to the query. Note that postgres query fails with duplicate names
        self.query_fields = set(self.info_fields).union(set([self.info_title]))

    def map_info(self):
        """Controller action that returns metadata about a given map.

        As a side effect this will set the content type to application/json

        @return: A JSON encoded string representing the metadata
        """
        # Specific parameters
        fetch_id = request.params.get('fetch_id')
        tile_url_base = 'http://{host}:{port}/database/{database}/table/{table}'.format(
            host=config['tiledmap.windshaft.host'],
            port=config['tiledmap.windshaft.port'],
            database=_get_engine().url.database,
            table=self.resource_id
        )

        ## Ensure we have at least one map style
        if not self.view['enable_plot_map'] and not self.view['enable_grid_map'] and not self.view['enable_heat_map']:
            return json.dumps({
                'geospatial': False,
                'fetch_id': fetch_id
            })

        # Prepare result
        quick_info_template_name = "{base}.{format}.mustache".format(
            base=self.quick_info_template,
            format=str(self.resource['format']).lower()
        )
        if not find_template(quick_info_template_name):
            quick_info_template_name = self.quick_info_template + '.mustache'
        info_template_name = "{base}.{format}.mustache".format(
            base=self.info_template,
            format=str(self.resource['format']).lower()
        )
        if not find_template(info_template_name):
            info_template_name = self.info_template + '.mustache'


        quick_info_template = toolkit.render(quick_info_template_name, {
            'title': self.info_title,
            'fields': self.info_fields
        })
        info_template = toolkit.render(info_template_name, {
            'title': self.info_title,
            'fields': self.info_fields,
            'overlapping_records_view': self.view['overlapping_records_view']
        })
        result = {
            'geospatial': True,
            'geom_count': 0,
            'total_count': 0,
            'bounds': ((83, -170), (-83, 170)),
            'zoom_bounds': {
                'min': int(config['tiledmap.zoom_bounds.min']),
                'max': int(config['tiledmap.zoom_bounds.max'])
            },
            'initial_zoom': {
                'min': int(config['tiledmap.initial_zoom.min']),
                'max': int(config['tiledmap.initial_zoom.max'])
            },
            'tile_layer': {
                'url': config['tiledmap.tile_layer.url'],
                'opacity': float(config['tiledmap.tile_layer.opacity'])
            },
            'repeat_map': self.repeat_map,
            'map_styles': {
            },
            'control_options': {
                'fullScreen': {
                    'position': 'topright'
                },
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
                                'color': '#F44',
                                'weight': 5,
                                'opacity': 0.5,
                                'fill': True,
                                'fillColor': '#F44',
                                'fillOpacity': 0.1
                            }
                        }
                    },
                    'position': 'topleft'
                },
                'selectCountry': {
                    'draw': {
                        'fill': '#F44',
                        'fill-opacity': '0.1',
                        'stroke': '#F44',
                        'stroke-opacity': '0.5'
                    }
                },
                'mapType': {
                    'position': 'bottomleft'
                },
                'miniMap': {
                    'position': 'bottomright',
                    'tile_layer': {
                        'url': config['tiledmap.tile_layer.url']
                    },
                    'zoomLevelFixed': 1,
                    #'zoomLevelOffset': -10,
                    'toggleDisplay': True,
                    'viewport': {
                        'marker_zoom': 8,
                        'rect': {
                            'weight': 1,
                            'color': '#00F',
                            'opacity': 1,
                            'fill': False
                        },
                        'marker': {
                            'weight': 1,
                            'color': '#00F',
                            'opacity': 1,
                            'radius': 3,
                            'fillColor': '#00F',
                            'fillOpacity': 0.2
                        }
                    }
                }
            },
            'plugin_options': {
                'tooltipInfo': {
                    'count_field': '_tiledmap_count',
                    'template': quick_info_template,
                },
                'tooltipCount': {
                    'count_field': '_tiledmap_count'
                },
                'pointInfo': {
                    'template': info_template,
                    'count_field': '_tiledmap_count'
                }
            },
            'fetch_id': fetch_id
        }

        if self.view['enable_heat_map']:
            result['map_styles']['heatmap'] = {
                'name': _('Heat Map'),
                'icon': '<i class="fa fa-fire"></i>',
                'controls': ['drawShape', 'mapType', 'fullScreen', 'miniMap'],
                'has_grid': False,
                'tile_source': {
                    'url': tile_url_base + '/{z}/{x}/{y}.png',
                    'params': {
                        'intensity': config['tiledmap.style.heatmap.intensity'],
                    }
                },
            }
            result['map_style'] = 'heatmap'

        if self.view['enable_grid_map']:
            result['map_styles']['gridded'] = {
                'name': _('Grid Map'),
                'icon': '<i class="fa fa-th"></i>',
                'controls': ['drawShape', 'mapType', 'fullScreen', 'miniMap'],
                'plugins': ['tooltipCount'],
                'has_grid': self.view['enable_utf_grid'],
                'grid_resolution': int(config['tiledmap.style.plot.grid_resolution']),
                'tile_source': {
                    'url': tile_url_base + '/{z}/{x}/{y}.png',
                    'params': {
                        'base_color': config['tiledmap.style.gridded.base_color']
                    }
                },
                'grid_source': {
                    'url': tile_url_base + '/{z}/{x}/{y}.grid.json',
                    'params': {
                        'interactivity': ','.join(self.query_fields)
                    }
                }
            }
            result['map_style'] = 'gridded'

        if self.view['enable_plot_map']:
            result['map_styles']['plot'] = {
                'name': _('Plot Map'),
                'icon': '<i class="fa fa-dot-circle-o"></i>',
                'controls': ['drawShape', 'mapType', 'fullScreen', 'miniMap'],
                'plugins': ['tooltipInfo', 'pointInfo'],
                'has_grid': self.view['enable_utf_grid'],
                'grid_resolution': int(config['tiledmap.style.plot.grid_resolution']),
                'tile_source': {
                    'url': tile_url_base + '/{z}/{x}/{y}.png',
                    'params': {
                        'fill_color': config['tiledmap.style.plot.fill_color'],
                        'line_color': config['tiledmap.style.plot.line_color']
                    }
                },
                'grid_source': {
                    'url': tile_url_base + '/{z}/{x}/{y}.grid.json',
                    'params': {
                        'interactivity': ','.join(self.query_fields)
                    }
                }
            }
            result['map_style'] = 'plot'

        info = self._get_data_info()
        result['total_count'] = info['total_count']
        result['geom_count'] = info['geom_count']
        if info['bounds']:
            result['bounds'] = info['bounds']

        response.headers['Content-type'] = 'application/json'
        return json.dumps(result)

    def _get_data_info(self):
        """Returns the specific map info for the current query

        Notes: We can't use datastore_search directly, as our query is too
               complex, but we still want to invoke the various plugins to
               ensure we get custom filters applied.

        @return: A dict defining three elements:
                 - count: Number of entries for current request
                 - geom_count: Number of entries that have a geom
                 - bounds: ((ymin, xmin), (ymax, xmax)
        """
        result = {}
        fields = self._get_request_fields()
        filters = self._get_request_filters()
        datastore_search = toolkit.get_action('datastore_search')
        data_dict = {
            'resource_id': self.resource_id,
            'filters': filters,
            'limit': 1,
            'q': urllib.unquote(request.params.get('q', '')),
            'fields': fields
        }
        # Get the total count and field types
        r = datastore_search({}, data_dict)
        if 'total' not in r or r['total'] == 0:
            return {
                'total_count': 0,
                'geom_count': 0,
                'bounds': None
            }
        result['total_count'] = r['total']
        field_types = dict([(f['id'], f['type']) for f in r['fields']])
        field_types['_id'] = 'int'
        # Call plugin to obtain correct where statement
        (ts_query, where_clause, values) = self._get_request_where_clause(data_dict, field_types)
        # Prepare and run our query
        query = """
            SELECT COUNT(r) AS count,
                   ST_YMIN(ST_EXTENT(r)) AS ymin,
                   ST_XMIN(ST_EXTENT(r)) AS xmin,
                   ST_YMAX(ST_EXTENT(r)) AS ymax,
                   ST_XMAX(ST_EXTENT(r)) AS xmax
            FROM   (
              SELECT "{geom_field}" AS r
              FROM   "{resource_id}" {ts_query}
              {where_clause}
            ) _tilemap_sub
        """.format(
            geom_field=self.geom_field_4326,
            resource_id=self.resource_id,
            where_clause=where_clause,
            ts_query=ts_query
        )
        if not is_single_statement(query):
            raise datastore_db.ValidationError({
                'query': ['Query is not a single statement.']
            })
        engine = _get_engine()
        with engine.begin() as connection:
            query_result = connection.execute(query, values)
            r = query_result.fetchone()

        result['geom_count'] = r['count']
        result['bounds'] = ((r['ymin'], r['xmin']), (r['ymax'], r['xmax']))
        return result

    def _get_request_fields(self):
        """Return the list of fields of the current request's resource"""
        fields = []
        engine = _get_engine()
        with engine.begin() as connection:
            r = connection.execute("""
                SELECT * FROM "{}" LIMIT 1
            """.format(self.resource_id))
            for field in r.cursor.description:
                if not field[0].startswith('_'):
                    fields.append(field[0].decode('utf-8'))
        fields.append(self.geom_field_4326)
        fields.append(self.geom_field)
        return fields

    def _get_request_filters(self):
        """Return a dict representing the filters of the current request"""
        filters = {}
        for f in urllib.unquote(request.params.get('filters', '')).split('|'):
            if f:
                (k, v) = f.split(':', 1)
                if k not in filters:
                    filters[k] = []
                filters[k].append(v)
        return filters

    def _get_request_where_clause(self, data_dict, field_types):
        """Return the where clause that applies to a query matching the given request

        @param data_dict: A dictionary representing a datastore API request
        @param field_types: A dictionary of field name to field type. Must
                            include all the fields that may be used in the
                            query
        @return: Tuple defining (
                    extra from statement for full text queries,
                    where clause,
                    list of replacement values
                )
        """
        query_dict = {
            'select': [],
            'sort': [],
            'where': []
        }
        for plugin in plugins.PluginImplementations(interfaces.IDatastore):
            query_dict = plugin.datastore_search(
                {}, data_dict, field_types, query_dict
            )
        clauses = []
        values = []
        for clause_and_values in query_dict['where']:
            clauses.append('(' + clause_and_values[0] + ')')
            values += clause_and_values[1:]

        where_clause = u' AND '.join(clauses)
        if where_clause:
            where_clause = u'WHERE ' + where_clause

        if 'ts_query' in query_dict and query_dict['ts_query']:
            ts_query = query_dict['ts_query']
        else:
            ts_query = ''

        return ts_query, where_clause, values
