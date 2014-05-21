import urllib
import cStringIO

from sqlalchemy.sql import select
from sqlalchemy import Table, Column, MetaData, String
from sqlalchemy import func, not_
from sqlalchemy.exc import ProgrammingError

import ckan.logic as logic
import ckan.lib.base as base
from ckan.common import json, request, _, response
from ckan.lib.render import find_template
import ckanext.tiledmap.lib.helpers as helpers
import ckanext.tiledmap.lib.tileconv as tileconv
from ckanext.tiledmap.lib.sqlgenerator import Select
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

    The configuration must include the following items:
    - ckan.datastore.write_url: The URL for the datastore database

    It may optionally define:
    - map.windshaft.host: The hostname of the windshaft server. Defaults to 127.0.0.1
    - map.windshaft.port: The port for the windshaft server. Defaults to 4000
    - map.winsdhaft_database: The database name to pass to the windshaft server. Defaults
        to the database name from the datastore URL.
    - map.geom_field: Geom field. Defaults to _the_geom_webmercator. Must be 3857 type field;
    - map.geom_field_4326: The 4326 geom field. Defaults to _geom ;
    - map.tile_layer.url: URL of the tile layer. Defaults to http://otile1.mqcdn.com/tiles/1.0.0/map/{z}/{x}/{y}.jpg
    - map.tile_layer.opacity: Opacity of the tile layer. Defaults to 0.8
    - map.initial_zoom.min: Minimum zoom level for initial display of dataset, defaults to 2
    - map.initial_zoom.max: Maximum zoom level for initial display of dataset, defaults to 6
    - map.info_template: Base name of the template to use to generate the popup info when clicking points.
        The template that will be used is <info template>.<resource type>.mustache if exists, and
        <info template>.mustache if not. For instance, given a base name of 'point_detail' and a resource of type 'csv',
        the template used will be point_detail.csv.mustache if it exists, and point_detail.mustache if not.

        Note that this template must return what itself is a mustache template, that will then get instantiated client
        side. The server side template has two variables: 'fields' (the fields selected by the view creator), and
        'title' (the title field selected by the view creator).

        Defaults to point_detail
    - map.quick_info_template: Base name of the template used for quick info on a record, typically shown on hover.
        See `map.info_template` for more information. Defaults to point_detail_hover.
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
        self.mss_options = {
            'plot': {
                'fill_color': config['tiledmap.style.plot.fill_color'],
                'line_color': config['tiledmap.style.plot.line_color'],
                'marker_size': int(config['tiledmap.style.plot.marker_size']),
                # Ideally half the marker size
                'grid_resolution': int(config['tiledmap.style.plot.grid_resolution'])
            },
            'gridded': {
                'base_color': config['tiledmap.style.gridded.base_color'],
                'marker_size': int(config['tiledmap.style.gridded.marker_size']),
                # Should really be the same as marker size!
                'grid_resolution': int(config['tiledmap.style.gridded.grid_resolution'])
            },
            'heatmap': {
                'intensity': float(config['tiledmap.style.heatmap.intensity']),
                'gradient': config['tiledmap.style.heatmap.gradient'],
                'marker_url': config['tiledmap.style.heatmap.marker_url'],
                'marker_size': int(config['tiledmap.style.heatmap.marker_size'])
            }
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
        self.info_fields = self.view['utf_grid_fields']
        self.info_template = config['tiledmap.info_template']
        self.quick_info_template = config['tiledmap.quick_info_template']

        # Fields that need to be added to the query. Note that postgres query fails with duplicate names
        self.query_fields = set(self.info_fields).union(set([self.info_title]))

    def _base_url(self, z, x, y, ext, query=None):
        """Return the base Windshaft URL that will serve the tiles and grids.

        @param z: the Z coordinate of the tile
        @param x: the X coordinate of the tile
        @param y: the Y coordinate of the tile
        @param ext: the Extension (.png/.grid.json) for the URL
        @param query: Dictionary defining a query string
        @rtype: str
        @return: The base windshaft URL that will serve the tile/overlay.
        """
        base = 'http://{host}:{port}/database/{database}/table/{table}/{z}/{x}/{y}.{ext}'.format(
            host=self.windshaft_host,
            port=self.windshaft_port,
            database=self.windshaft_database,
            table=self.resource_id,
            z=z,
            x=x,
            y=y,
            ext=ext
        )
        if query is not None and len(query):
            return base + "?" + urllib.urlencode(query)
        else:
            return base

    def _tile_url(self, z, x, y, sql='', style='', query=None):
        """Return the tile Windshaft URL.

        @param z: the Z coordinate of the tile
        @param x: the X coordinate of the tile
        @param y: the Y coordinate of the tile
        @param sql: the SQL query to pass on to Windshaft
        @param style: the Style to pass on to Windshaft
        @rtype: str
        @return: The Winsdhaft URL that will serve a tile
        """
        if query is None:
            query = {}
        if sql:
            query['sql'] = sql
        if style:
            query['style'] = style
        return self._base_url(z, x, y, 'png', query)

    def _grid_url(self, z, x, y, callback='', sql='', interactivity='', query=None):
        """Return the grid windshaft URL.

        @param z: the Z coordinate of the tile
        @param x: the X coordinate of the tile
        @param y: the Y coordinate of the tile
        @param callback: Javascript callback function.
        @param sql: Sql to provide to the server.
        @param interactivity: SQL fields to make available to the front end (for info box, hover, etc.)
        @param query: A dictionary defining any other query strings for the URL
        @rtype: str
        @return: The Windshaft URL that will serve a grid.
        """
        if query is None:
            query = {}
        if callback:
            query['callback'] = callback
        if sql:
            query['sql'] = sql
        if interactivity:
            query['interactivity'] = interactivity
        return self._base_url(z, x, y, 'grid.json', query)

    def _base_query(self, z, x, y, filters, fulltext, geom, marker_size, grid_size=4):
        """Return a base SqlGenerator Select query with components that are common to all styles of grid and tile
        queries
        @param filters: List of filters for the request
        @param geom: Geometry filter for the request
        @param grid_size: Grid size for the request (grid tiles only)
        @return: sqlgenerator.Select object
        """
        query = Select(options={'compact': True}, identifiers={
            'resource': self.resource_id,
            'geom_field': (self.resource_id, self.geom_field),
            'geom_field_label': self.geom_field,
            'geom_field_4326': (self.resource_id, self.geom_field_4326),
            'geom_field_4326_label': self.geom_field_4326
        }, values={
            'grid_size': grid_size,
            'marker_size': marker_size
        })
        query.select_from('{resource}')

        if filters:
            for input_filters in json.loads(filters):
                # TODO - other types of filters
                if input_filters['type'] == 'term':
                    query.where("{field} = {value}", identifiers={
                        'field': (self.resource_id, input_filters['field'])
                    }, values={
                        'value': input_filters['term']
                    })

        if fulltext:
            query.where('_full_text @@ plainto_tsquery({search})', values={
                'language': 'english',
                'search': fulltext
            })

        if geom:
            query.where("ST_Intersects({geom_field}, ST_Transform(ST_GeomFromText({geom}, 4326), 3857))", values={
                'geom': geom
            })

        # Find bounding box based on tile X,Y,Z
        bbox = tileconv.tile_to_latlng_bbox(float(x), float(y), float(z))
        query.where('''
            ST_Intersects({geom_field}, ST_Expand(
                ST_Transform(
                    ST_SetSrid(
                        ST_MakeBox2D(
                            ST_Makepoint({lng0}, {lat0}),
                            ST_Makepoint({lng1}, {lat1})
                        ),
                    4326),
                3857), !pixel_width! * {marker_radius}))''', values={
            'lng0': bbox[0][1],
            'lat0': bbox[0][0],
            'lng1': bbox[1][1],
            'lat1': bbox[1][0],
            'marker_radius': marker_size/2.0
        })

        return query

    def _get_style_options(self, style):
        """For a given map style, return the options for the template looking at global and view settings"""
        options = self.mss_options[style].copy()
        if style == 'plot':
            options['fill_color'] = self.view['plot_marker_color']
            options['line_color'] = self.view['plot_marker_line_color']
        elif style == 'gridded':
            options['base_color'] = self.view['grid_base_color']
        elif style == 'heatmap':
            options['intensity'] = self.view['heat_intensity']
        return options

    def tile(self, z, x, y):
        """Controller action that returns a map tile

        As a side effect this will set the content type to image/png

        @param x: The X coordinate of the tile
        @param y: The Y coordinate of the tile
        @param z: The Z coordinate of the tile
        @rtype: cStringIO.StringIO
        @return: A PNG image representing the required style
        """

        filters = request.params.get('filters')
        fulltext = request.params.get('q')
        geom = request.params.get('geom')
        style = request.params.get('style')

        if not style:
            style = 'plot'
        if style not in ['plot', 'gridded', 'heatmap']:
            base.abort(400, _("Incorrect style parameter"))

        query = self._base_query(z, x, y, filters, fulltext, geom, self.mss_options[style]['marker_size'])

        # If we're drawing dots, then we can ignore the ones with identical positions by
        # selecting DISTINCT ON (_the_geom_webmercator), but we need keep them for heatmaps
        # to get the right effect.
        # This provides a performance improvement for datasets with many points that share identical
        # positions. Note that there's an overhead to doing so for small datasets, and also that
        # it only has an effect for records with *identical* geometries.
        if style == 'heatmap':
            query.select('{geom_field}')
            # no need to shuffle (see below), so use the subquery directly
            sql = query.to_sql()
        elif style == 'gridded':
            query.select("ST_SnapToGrid({geom_field}, !pixel_width! * {marker_size}" ", !pixel_height! * {marker_size})"
                         " AS {geom_field_label}")
            query.select("COUNT({geom_field}) AS count")
                        # The group by needs to match the column chosen above, including by the size of the grid
            query.group_by('ST_SnapToGrid({geom_field}, !pixel_width! * {marker_size}, !pixel_height! * {marker_size})')
            query.order_by('count DESC')

            outer_q = Select(options={'compact': True}, identifiers={
                'geom_field_label': self.geom_field
            })
            outer_q.select_from('({query}) AS _mapplugin_sub', values={'query': query})
            outer_q.select('count')
            outer_q.select('{geom_field_label}')
            outer_q.order_by('random()')
            sql = outer_q.to_sql()
        else:
            query.select('{geom_field}')
            query.distinct_on('{geom_field}')
            # The SELECT ... DISTINCT ON query silently orders the results by lat and lon which leads to a nasty
            # overlapping effect when rendered. To avoid this, we shuffle the points in an outer
            # query.
            outer_q = Select(options={'compact': True}, identifiers={
                'geom_field_label': self.geom_field
            })
            outer_q.select_from('({query}) AS _mapplugin_sub', values={'query': query})
            outer_q.select('{geom_field_label}')
            outer_q.order_by('random()')
            sql = outer_q.to_sql()

        mss_options = self._get_style_options(style)
        mss_options['resource_id'] = self.resource_id
        mss = base.render('mss/{}.mss'.format(style), mss_options)

        url = self._tile_url(z, x, y, sql=sql, style=mss)
        response.headers['Content-type'] = 'image/png'
        tile = cStringIO.StringIO(urllib.urlopen(url).read())
        return tile

    def grid(self, z, x, y):
        """Controller action that returns a json grid

        As a side effect this will set the content type to text/javascript

        @param x: The X coordinate of the tile
        @param y: The Y coordinate of the tile
        @param z: The Z coordinate of the tile
        @rtype: cStringIO.StringIO
        @return: A JSON encoded string representing the tile's grid
        """

        filters = request.params.get('filters')
        fulltext = request.params.get('q')
        geom = request.params.get('geom')
        callback = request.params.get('callback')
        style = request.params.get('style')

        if not style:
            style = 'plot'
        if style not in ['plot', 'gridded', 'heatmap']:
            base.abort(400, _("Incorrect style parameter"))

        # To calculate the number of overlapping points, we first snap them to a grid roughly four pixels wide, and then
        # group them by that grid. This allows us to count the records, but we need to aggregate the rest of the
        # information in order to later return the "top" record from the stack of overlapping records
        query = self._base_query(z, x, y, filters, fulltext, geom,
                                 self.mss_options[style]['marker_size'],
                                 self.mss_options[style]['grid_resolution'])
        for col in self.query_fields:
            query.select('array_agg({col}) AS {col}', identifiers={
                'col': col
            })
        query.select('COUNT({geom_field}) AS count')
        query.select('array_agg({geom_field_4326}) AS {geom_field_4326_label}')
        query.select('ST_SnapToGrid({geom_field}, !pixel_width! * {grid_size}, !pixel_height! * {grid_size}) AS _mapplugin_center')

        # The group by needs to match the column chosen above, including by the size of the grid
        query.group_by('ST_SnapToGrid({geom_field}, !pixel_width! * {grid_size}, !pixel_height! * {grid_size})')
        query.order_by('count DESC')

        # In the outer query we can use the overlapping records count and the location, but we also need to pop the
        # first record off of the array. If we were to return e.g. all the overlapping names, the json grids would
        # unbounded in size.

        outer_query = Select(options={'compact': True}, identifiers={
            'resource': self.resource_id,
            'geom_field_label': self.geom_field,
            'geom_field_4326_label': self.geom_field_4326,
        }, values={
            'query': query
        })

        outer_query.select_from('({query}) AS _mapplugin_sub')
        for col in self.query_fields:
            outer_query.select('{col}[1] AS {col}', identifiers={
                'col': col
            })
        outer_query.select('count')
        outer_query.select('st_y({geom_field_4326_label}[1]) AS lat')
        outer_query.select('st_x({geom_field_4326_label}[1]) AS lng')
        outer_query.select('_mapplugin_center AS {geom_field_label}')
        sql = outer_query.to_sql()

        interactivity_fields = ",".join(set(list(self.query_fields) + ['count', 'lat', 'lng']))
        url = self._grid_url(z, x, y, callback=callback, sql=sql, interactivity=interactivity_fields)
        response.headers['Content-type'] = 'text/javascript'
        # TODO: Detect if the incoming connection has been dropped, and if so stop the query.
        grid = cStringIO.StringIO(urllib.urlopen(url).read())
        return grid

    def map_info(self):
        """Controller action that returns metadata about a given map.

        As a side effect this will set the content type to application/json

        @return: A JSON encoded string representing the metadata
        """
        # Specific parameters
        filters = request.params.get('filters')
        fetch_id = request.params.get('fetch_id')

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

        if filters:
            for input_filters in json.loads(filters):
                # TODO - other types of filters
                if input_filters['type'] == 'term':
                    geo_table.append_column(Column(input_filters['field'], String(255)))
                    query = query.where(geo_table.c[input_filters['field']] == input_filters['term'])

        # Prepare result
        quick_info_template_name = "{base}.{format}.mustache".format(
            base=self.quick_info_template,
            format=self.resource['format']
        )
        if not find_template(quick_info_template_name):
            quick_info_template_name = self.quick_info_template + '.mustache'
        info_template_name = "{base}.{format}.mustache".format(
            base=self.info_template,
            format=self.resource['format']
        )
        if not find_template(info_template_name):
            info_template_name = self.info_template + '.mustache'


        quick_info_template = base.render(quick_info_template_name, {
            'title': self.info_title,
            'fields': self.info_fields
        })
        info_template = base.render(info_template_name, {
            'title': self.info_title,
            'fields': self.info_fields
        })
        result = {
            'geospatial': True,
            'geom_count': 0,
            'bounds': ((51.496830, -0.178812), (51.496122, -0.173877)),
            'initial_zoom': self.initial_zoom,
            'tile_layer': self.tile_layer,
            'map_styles': {
            },
            'control_options': {
                'drawShape': {
                    'draw': {
                        'polyline': False,
                        'marker': False,
                        'circle': False
                    },
                    'position': 'topleft'
                },
                'mapType': {
                    'position': 'bottomleft'
                }
            },
            'plugin_options': {
                'tooltipInfo': {
                    'count_field': 'count',
                    'template': quick_info_template,
                },
                'tooltipCount': {
                    'count_field': 'count'
                },
                'pointInfo': {
                    'template': info_template,
                    'count_field': 'count'
                }
            },
            'fetch_id': fetch_id
        }

        if self.view['enable_heat_map']:
            result['map_styles']['heatmap'] = {
                'name': _('Distribution Map'),
                'icon': 'D',
                'controls': ['drawShape', 'mapType'],
                'has_grid': False,
            }
            result['map_style'] = 'heatmap'

        if self.view['enable_grid_map']:
            result['map_styles']['gridded'] = {
                'name': _('Grid Map'),
                'icon': 'G',
                'controls': ['drawShape', 'mapType'],
                'plugins': ['tooltipCount'],
                'has_grid': self.view['enable_utf_grid'],
                'grid_resolution': self.mss_options['plot']['grid_resolution']
            }
            result['map_style'] = 'gridded'

        if self.view['enable_plot_map']:
            result['map_styles']['plot'] = {
                'name': _('Plot Map'),
                'icon': 'P',
                'controls': ['drawShape', 'mapType'],
                'plugins': ['tooltipInfo', 'pointInfo'],
                'has_grid': self.view['enable_utf_grid'],
                'grid_resolution': self.mss_options['plot']['grid_resolution']
            }
            result['map_style'] = 'plot'

        inner_query = query.column(geo_table.c[self.geom_field_4326].label('r')).alias('_mapplugin_sub')
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

        response.headers['Content-type'] = 'application/json'
        return json.dumps(result)