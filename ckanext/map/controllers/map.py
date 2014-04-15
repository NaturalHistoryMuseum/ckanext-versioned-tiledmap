import urllib
import cStringIO

from pylons import config
from sqlalchemy.sql import select
from sqlalchemy import Table, Column, Integer, String, MetaData
from sqlalchemy import create_engine
import geoalchemy.functions as geo_functions
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import func, not_
from sqlalchemy.sql import desc
from sqlalchemy.exc import ProgrammingError

import ckan.logic as logic
import ckan.lib.base as base
from ckan.common import json, request, _, response
import ckanext.map.lib.helpers as helpers

import ckan.lib.base as base


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
    - map.info_fields: Comma separated list of "label:field" SQL fields that should be made available to the templates;
    - map.title_template: Name of the template used to generate the info sidebar title. The template is rendered with
        info_fields available as a list of (label,field) tuples, and should return a Mustache template which can then
        be rendered client side. All the values of the fields in info_fields are available during client side rendering.
        In addition the fiels 'count', 'lat', 'lng' and 'multiple' are also available.
         Defaults to point_detail_title.mustache ;
    - map.info_template: Name of the template to use for generating point info detail in the sidebar.
        The template is rendered with 'info_fields' and 'title_template'. See map.title_template.
        Defaults to point_detail.dwc.mustache;
    - map.quick_info_template: Name of the template to use for generating hover information. The template is rendered
        with 'info_fields' available. See map.title_template. Defaults to point_detail_hover.mustache;
    """

    def __init__(self):
        """Setup the controller's variables

        Actual values are assigned during __before__
        """
        self.windshaft_host = '127.0.0.1'
        self.windshaft_port = '4000'
        self.windshaft_database = ''
        self.engine = None
        self.resource_id = ''
        self.geom_field = ''
        self.geom_field_4326 = ''
        self.tile_layer = {}
        self.initial_zoom = {}
        self.mss_options = {}
        self.info_fields = {}
        self.query_fields = []
        self.title_template = ''
        self.info_template = ''
        self.quick_info_template = ''

    def __before__(self, action, **params):
        """Setup the request

        This will return a 500 error if there are missing configuration items, and a 400
        error if the resource_id parameter is missing.
        """
        # Run super and setup engine
        super(MapController, self).__before__(action, **params)
        try:
            self.engine = create_engine(config['ckan.datastore.write_url'])
        except KeyError:
            base.abort(500, _("Missing configuration options"))

        # Read configuration
        self.windshaft_host = config.get('map.windshaft.host', '127.0.0.1')
        self.windshaft_port = config.get('map.windshaft.port', '4000')
        self.windshaft_database = config.get('map.windshaft.database', None) or self.engine.url.database
        info_field_list = config.get('map.info_fields', 'Record:_id,Scientific Name:scientificName,Kingdom:kingdom,Phylum:phylum,Class:class,Order:order,Family:family,Genus:genus,Subgenus:subgenus,Institution Code:institutionCode,Catalogue Number:catalogNumber,Collection Code:collectionCode,Identified By:identifiedBy,Date:dateIdentified,Continent:continent,Country:country,State/Province:stateProvince,County:county,Locality:locality,Habitat:habitat').split(',')
        self.info_fields = [(l, v) for l, v in (a.split(':') for a in info_field_list)]
        self.info_template = config.get('map.info_template', 'point_detail.dwc.mustache')
        self.title_template = config.get('map.title_template', 'point_detail_title.dwc.mustache')
        self.quick_info_template = config.get('map.quick_info_template', 'point_detail_hover.dwc.mustache')
        self.geom_field = config.get('map.geom_field', '_the_geom_webmercator')
        self.geom_field_4326 = config.get('map.geom_field_4326', '_geom')
        self.tile_layer = {
            'url': config.get('map.tile_layer.url', 'http://otile1.mqcdn.com/tiles/1.0.0/map/{z}/{x}/{y}.jpg'),
            'opacity': config.get('map.tile_layer.opacity', '0.8')
        }
        self.initial_zoom = {
            'min': config.get('map.initial_zoom.min', 2),
            'max': config.get('map.initial_zoom.max', 6)
        }
        self.mss_options = {
            'fill_color': config.get('map.style.plot.fill_color', '#EE0000'),
            'line_color': config.get('map.style.plot.line_color', '#FFFFFF'),
            'grid_base_color': config.get('map.style.gridded.base_color', '#F02323'),
            'heatmap_gradient': config.get('map.style.heatmap.gradient',
                                           '#0000FF, #00FFFF, #00FF00, #FFFF00, #FFA500, #FF0000')
        }

        # Get request resource_id
        if not request.params.get('resource_id'):
            base.abort(400, _("Missing resource id"))

        self.resource_id = request.params.get('resource_id')
        try:
            logic.get_action('resource_show')(None, {'id': self.resource_id})
        except logic.NotFound:
            base.abort(404, _('Resource not found'))
        except logic.NotAuthorized:
            base.abort(401, _('Unauthorized to read resources'))

        # Fields that need to be added to the query. Note that postgres query fails with duplicate names
        self.query_fields = set([v for (l, v) in self.info_fields])

        # Build the list of columns needed for this request
        self._request_columns()

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

    def _request_columns(self):
        """Setup a dict of SQLAlchemy columns needed for the current request

        We don't use reflection for this as SqlAlchemy doesn't support materialized views.
        """
        self.columns = {}
        # Add geom columns
        self.columns[self.geom_field] = Column(self.geom_field, helpers.Geometry)
        self.columns[self.geom_field_4326] = Column(self.geom_field_4326, helpers.Geometry)
        # Add filter columns. Note that this will fail for integer and date fields - however
        # that is how the datastore queries are build, so we replicate the behaviour here.
        filters = request.params.get('filters')
        if filters:
            for input_filters in json.loads(filters):
                # TODO - other types of filters
                if input_filters['type'] == 'term':
                    self.columns[input_filters['field']] = Column(input_filters['field'], String(255))

        # Add all the fields we want for this query.
        for column_name in self.query_fields:
            self.columns[column_name] = Column(column_name, String(255))


    def _geo_table(self):
        """Return the table used to build the Windshaft query

        @rtype: Table
        @return: Return the SQLAlchemy table corresponding to the geo table in Windshaft
        """
        metadata = MetaData()
        table = Table(self.resource_id, metadata, *self.columns.values())
        return table

    def tile(self, z, x, y):
        """Controller action that returns a map tile

        As a side effect this will set the content type to image/png

        @param x: The X coordinate of the tile
        @param y: The Y coordinate of the tile
        @param z: The Z coordinate of the tile
        @rtype: cStringIO.StringIO
        @return: A PNG image representing the required style
        """

        resource_id = request.params.get('resource_id')
        filters = request.params.get('filters')
        geom = request.params.get('geom')
        style = request.params.get('style')

        if not style:
            style = 'plot'
        if style not in ['plot', 'gridded', 'heatmap']:
            base.abort(400, _("Incorrect style parameter"))

        geo_table = self._geo_table()

        width = helpers.MapnikPlaceholderColumn('pixel_width')
        height = helpers.MapnikPlaceholderColumn('pixel_height')

        # If we're drawing dots, then we can ignore the ones with identical positions by
        # selecting DISTINCT ON (_the_geom_webmercator), but we need keep them for heatmaps
        # to get the right effect.
        # This provides a performance improvement for datasets with many points that share identical
        # positions. Note that there's an overhead to doing so for small datasets, and also that
        # it only has an effect for records with *identical* geometries.
        if style == 'heatmap':
            sub = select([geo_table.c[self.geom_field]])
        elif style == 'gridded':
            sub = select([func.count(geo_table.c[self.geom_field]).label('count'),
                          func.ST_SnapToGrid(geo_table.c[self.geom_field], width * 8, height * 8).label(
                              self.geom_field)])
        else:
            sub = select([geo_table.c[self.geom_field].label(self.geom_field)],
                         distinct=self.geom_field,
                         from_obj=geo_table)

        if filters:
            for input_filters in json.loads(filters):
                # TODO - other types of filters
                if input_filters['type'] == 'term':
                    sub = sub.where(geo_table.c[input_filters['field']] == input_filters['term'])

        if geom:
            sub = sub.where(
                geo_functions.intersects(geo_table.c[self.geom_field], geo_functions.transform(geom, 3857))
            )

        if style == 'heatmap':
            # no need to shuffle (see below), so use the subquery directly
            sql = helpers.interpolateQuery(sub, self.engine)
        elif style == 'gridded':
            sub = sub.where(func.ST_Intersects(geo_table.c[self.geom_field],
                                               func.ST_SetSrid(helpers.MapnikPlaceholderColumn('bbox'), 3857)))

            # The group by needs to match the column chosen above, including by the size of the grid
            sub = sub.group_by(func.ST_SnapToGrid(geo_table.c[self.geom_field], width * 8, height * 8))
            sub = sub.order_by(desc('count')).alias('_mapplugin_sub')

            outer = select(['count', self.geom_field]).select_from(sub).order_by(func.random())
            sql = helpers.interpolateQuery(outer, self.engine)
        else:
            # The SELECT ... DISTINCT ON query silently orders the results by lat and lon which leads to a nasty
            # overlapping effect when rendered. To avoid this, we shuffle the points in an outer
            # query.

            sub = sub.alias('_mapplugin_sub')
            outer = select([self.geom_field]).select_from(sub).order_by(func.random())
            sql = helpers.interpolateQuery(outer, self.engine)

        mss_options = self.mss_options.copy()
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

        callback = request.params.get('callback')
        filters = request.params.get('filters')
        geom = request.params.get('geom')
        style = request.params.get('style')

        geo_table = self._geo_table()

        if style == 'gridded':
            grid_size = 8
        else:
            grid_size = 4

        # Set mapnik placeholders for the size of each pixel. Allows the grid to adjust automatically to the pixel size
        # at whichever zoom we happen to be at.
        width = helpers.MapnikPlaceholderColumn('pixel_width')
        height = helpers.MapnikPlaceholderColumn('pixel_height')

        # To calculate the number of overlapping points, we first snap them to a grid roughly four pixels wide, and then
        # group them by that grid. This allows us to count the records, but we need to aggregate the rest of the
        # information in order to later return the "top" record from the stack of overlapping records

        sub_cols = []
        for i in self.query_fields:
            sub_cols.append(func.array_agg(geo_table.c[i]).label(i))
        sub_cols.append(func.count(geo_table.c[self.geom_field]).label('count'))
        sub_cols.append(func.array_agg(geo_table.c[self.geom_field_4326]).label(self.geom_field_4326))
        sub_cols.append(func.ST_SnapToGrid(geo_table.c[self.geom_field], width * grid_size, height * grid_size).label(
            '_mapplugin_center'
        ))

        # Filter the records by department, using any filters, and by the geometry drawn
        sub = select(sub_cols)

        if filters:
            for filter in json.loads(filters):
                # TODO - other types of filters
                if filter['type'] == 'term':
                    sub = sub.where(geo_table.c[filter['field']] == filter['term'])

        if geom:
            sub = sub.where(
                geo_functions.intersects(geo_table.c[self.geom_field], geo_functions.transform(geom, 3857))
            )

        # We need to also filter the records to those in the area that we're looking at, otherwise the query causes
        # every record in the database to be snapped to the grid. Mapnik can fill in the !bbox! token for us, which
        # saves us trying to figure it out from the z/x/y numbers here.
        sub = sub.where(func.ST_Intersects(geo_table.c[self.geom_field],
                                           func.ST_SetSrid(helpers.MapnikPlaceholderColumn('bbox'), 3857)))

        # The group by needs to match the column chosen above, including by the size of the grid
        sub = sub.group_by(func.ST_SnapToGrid(geo_table.c[self.geom_field], width * grid_size, height * grid_size))
        sub = sub.order_by(desc('count')).alias('_mapplugin_sub')

        # In the outer query we can use the overlapping records count and the location, but we also need to pop the
        # first record off of the array. If we were to return e.g. all the overlapping names, the json grids would
        # unbounded in size.

        # Note that the c.foo[1] syntax needs SQLAlchemy >= 0.8
        # However, geoalchemy breaks on SQLAlchemy >= 0.9, so be careful.

        outer_cols = []
        for i in self.query_fields:
                outer_cols.append(Column(i, ARRAY(String))[1].label(i))
        # Always include count/lat/lng as various plugins excpet those.
        outer_cols.append(Column('count', Integer))
        outer_cols.append(func.st_y(Column(self.geom_field_4326, ARRAY(helpers.Geometry))[1]).label('lat'))
        outer_cols.append(func.st_x(Column(self.geom_field_4326, ARRAY(helpers.Geometry))[1]).label('lng'))
        outer_cols.append(Column('_mapplugin_center', helpers.Geometry).label(self.geom_field))

        s = select(outer_cols).select_from(sub)
        sql = helpers.interpolateQuery(s, self.engine)
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
        # Setup query
        filters = request.params.get('filters')
        fetch_id = request.params.get('fetch_id')

        geo_table = self._geo_table()

        query = select(bind=self.engine)
        query = query.where(not_(geo_table.c[self.geom_field] == None))

        if filters:
            for input_filters in json.loads(filters):
                # TODO - other types of filters
                if input_filters['type'] == 'term':
                    query = query.where(geo_table.c[input_filters['field']] == input_filters['term'])

        # Prepare result
        title_template = base.render(self.title_template, {'info_fields': self.info_fields})
        quick_info_template = base.render(self.quick_info_template, {'info_fields': self.info_fields})
        info_template = base.render(self.info_template, {
            'info_fields': self.info_fields,
            'title_template': title_template
        })
        result = {
            'geospatial': True,
            'geom_count': 0,
            'bounds': ((51.496830, -0.178812), (51.496122, -0.173877)),
            'initial_zoom': self.initial_zoom,
            'tile_layer': self.tile_layer,
            'map_styles': {
                'plot': {
                    'name': _('Plot Map'),
                    'icon': 'P',
                    'controls': ['drawShape', 'mapType'],
                    'plugins': ['tooltipInfo', 'pointInfo']
                },
                'heatmap': {
                    'name': _('Distribution Map'),
                    'icon': 'D',
                    'controls': ['drawShape', 'mapType'],
                },
                'gridded': {
                    'name': _('Grid Map'),
                    'icon': 'G',
                    'controls': ['drawShape', 'mapType'],
                    'plugins': ['tooltipCount']
                }
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
            'map_style': 'plot',
            'fetch_id': fetch_id
        }

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
            query_result = self.engine.execute(outer_query)
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