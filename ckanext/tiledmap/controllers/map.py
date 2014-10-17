import re
import urllib

from sqlalchemy.sql import select
from sqlalchemy import Table, Column, MetaData, String
from sqlalchemy import func, not_
from sqlalchemy.exc import ProgrammingError

import ckan.logic as logic
import ckan.lib.base as base
from ckan.common import json, request, _, response
from ckan.lib.render import find_template
import ckanext.tiledmap.lib.helpers as helpers
from ckanext.tiledmap.db import _get_engine
from ckanext.tiledmap.config import config


class MapController(base.BaseController):
    """Controller for displaying map tiles and grids

    This controller serves map tiles and json grids served from the following URLs:

    - /map-tile/{z}/{x}/{y}.png
    - /map-grid/{z}/{x}/{y}/grid.json

    Both request will expect a 'resource_id' parameter, and may optionally have:
    - filter, defining the filters to apply ;
    - geom, defining the geometry to apply ;
    - style, defining the map style (either 'heatmap', 'gridded' or nothing for the dot map)

    In addition, this controller serves meta-information about a particular map at the following URL:

    - /map-info

    This request expects a 'resource_id' parameter, and may optionally have:

    - filter, defining the filters to apply.

    See ckanext.tiledmap.config for configuration options.
    """

    def __init__(self):
        """Setup the controller's parameters that are not request-dependent
        """
        # Read configuration
        self.windshaft_host = config['tiledmap.windshaft.host']
        self.windshaft_port = config['tiledmap.windshaft.port']
        self.windshaft_database = _get_engine().url.database
        self.geom_field = config['tiledmap.geom_field']
        self.geom_field_4326 = config['tiledmap.geom_field_4326']
        self.tile_layer = {
            'url': config['tiledmap.tile_layer.url'],
            'opacity': float(config['tiledmap.tile_layer.opacity'])
        }
        self.initial_zoom = {
            'min': int(config['tiledmap.initial_zoom.min']),
            'max': int(config['tiledmap.initial_zoom.max'])
        }
        self.zoom_bounds = {
            'min': int(config['tiledmap.zoom_bounds.min']),
            'max': int(config['tiledmap.zoom_bounds.max'])
        }
        self.mss_options = {
            'plot': {
                'grid_resolution': int(config['tiledmap.style.plot.grid_resolution'])
            },
            'gridded': {
                'grid_resolution': int(config['tiledmap.style.gridded.grid_resolution'])
            },
        }
        # Empty values for request dependent parameters
        self.resource_id = ''
        self.resource = None
        self.view_id = ''
        self.view = None
        self.info_title = ''
        self.info_fields = []
        self.info_template = ''
        self.title_template = ''
        self.quick_info_template = ''
        self.query_fields = []

    def __before__(self, action, **params):
        """Setup the request

        This will trigger a 400 error if the resource_id parameter is missing.
        """
        # Run super
        super(MapController, self).__before__(action, **params)

        # Get request resource_id
        if not request.params.get('resource_id'):
            base.abort(400, _("Missing resource id"))

        self.resource_id = request.params.get('resource_id')

        try:
            self.resource = logic.get_action('resource_show')(None, {'id': self.resource_id})
        except logic.NotFound:
            base.abort(404, _('Resource not found'))
        except logic.NotAuthorized:
            base.abort(401, _('Unauthorized to read resources'))
        self.view_id = request.params.get('view_id')
        self.view = logic.get_action('resource_view_show')(None, {'id': self.view_id})

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
        filter_str = urllib.unquote(request.params.get('filters', ''))
        fetch_id = request.params.get('fetch_id')
        tile_url_base = 'http://{host}:{port}/database/{database}/table/{table}'.format(
            host=self.windshaft_host,
            port=self.windshaft_port,
            database=self.windshaft_database,
            table=self.resource_id
        )

        ## Ensure we have at least one map style
        if not self.view['enable_plot_map'] and not self.view['enable_grid_map'] and not self.view['enable_heat_map']:
            return json.dumps({
                'geospatial': False,
                'fetch_id': fetch_id
            })

        # Setup query
        engine = _get_engine()
        metadata = MetaData()
        geo_table = Table(self.resource_id, metadata, Column(self.geom_field, helpers.Geometry),
                          Column(self.geom_field_4326, helpers.Geometry))

        query = select(bind=engine)
        query = query.where(not_(geo_table.c[self.geom_field] == None))
        total_count_query = select([func.count(1).label('count')], bind=engine, from_obj=geo_table)

        # Add filters
        if filter_str:
            for f in filter_str.split('|'):
                try:
                    (name, value) = f.split(':')
                    if name == '_tmgeom':
                        query = query.where(
                            func.st_intersects(
                                geo_table.c[self.geom_field],
                                func.st_transform(
                                    func.st_geomfromtext(value, 4326),
                                    3857
                                )
                            )
                        )
                    else:
                        geo_table.append_column(Column(name, String(255)))
                        query = query.where(geo_table.c[name] == value)
                        total_count_query = total_count_query.where(geo_table.c[name] == value)
                except ValueError:
                    pass

        fulltext = urllib.unquote(request.params.get('q', ''))
        if fulltext:
            # Simulate plainto_tsquery as SQLAlchemy only generates ts_query.
            fulltext = re.sub('([^\s]|^)\s+([^\s]|$)', '\\1&\\2', fulltext.strip())
            geo_table.append_column(Column('_full_text', String(255)))
            query = query.where(geo_table.c['_full_text'].match(fulltext))
            total_count_query = total_count_query.where(geo_table.c['_full_text'].match(fulltext))

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


        quick_info_template = base.render(quick_info_template_name, {
            'title': self.info_title,
            'fields': self.info_fields
        })
        info_template = base.render(info_template_name, {
            'title': self.info_title,
            'fields': self.info_fields,
            'overlapping_records_view': self.view['overlapping_records_view']
        })
        result = {
            'geospatial': True,
            'geom_count': 0,
            'total_count': 0,
            'bounds': ((83, -170), (-83, 170)),
            'zoom_bounds': self.zoom_bounds,
            'initial_zoom': self.initial_zoom,
            'tile_layer': self.tile_layer,
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
                    'tile_layer': self.tile_layer,
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
                'name': _('Distribution Map'),
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
                'grid_resolution': self.mss_options['plot']['grid_resolution'],
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
                'grid_resolution': self.mss_options['plot']['grid_resolution'],
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

        inner_query = query.column(geo_table.c[self.geom_field_4326].label('r')).alias('_tiledmap_sub')
        inner_col = Column('r', helpers.Geometry)
        outer_query = select([
            func.count(inner_col).label('count'),
            func.st_ymin(func.st_extent(inner_col)).label('ymin'),
            func.st_xmin(func.st_extent(inner_col)).label('xmin'),
            func.st_ymax(func.st_extent(inner_col)).label('ymax'),
            func.st_xmax(func.st_extent(inner_col)).label('xmax')
        ]).select_from(inner_query)
        try:
            query_result = engine.execute(outer_query)
        except ProgrammingError:
            response.headers['Content-type'] = 'application/json'
            return json.dumps({
                'geospatial': False,
                'fetch_id': fetch_id
            })

        row = query_result.fetchone()
        result['geom_count'] = row['count']
        if row['xmin'] is not None:
            result['bounds'] = ((row['ymin'], row['xmin']), (row['ymax'], row['xmax']))
        query_result.close()

        # Now fetch the number of rows that would be displayed in the grid (current + those withou geometries)
        try:
            query_result = engine.execute(total_count_query)
            row = query_result.fetchone()
            result['total_count'] = row['count']
        except ProgrammingError:
            result['total_count'] = 0

        response.headers['Content-type'] = 'application/json'
        return json.dumps(result)