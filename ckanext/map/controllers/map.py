import urllib
import cStringIO

from pylons import config
from sqlalchemy.sql import select
from sqlalchemy import Table, Column, Integer, String, MetaData
from sqlalchemy import create_engine
import geoalchemy.functions as geo_functions
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import func
from sqlalchemy.sql import desc

import ckan.logic as logic
import ckan.lib.base as base
from ckan.common import json, request, _, response
import ckanext.map.lib.helpers as helpers


class MapController(base.BaseController):
    """Controller for displaying map tiles and grids

    This controller serves map tiles and json grids served from the following URLs:

    - /map-tile/{z}/{x}/{y}.png
    - /map-grid/{z}/{x}/{y}/grid.json

    Both request will expect a 'resource_id' parameter, and may optionally have:
    - filter, defining the filters to apply ;
    - geom, defining the geometry to apply ;
    - style, defining the style to apply ;

    The configuration must include the following items:
    - ckan.datastore.write_url: The URL for the datastore database

    It may optionally define:
    - map.windshaft.host: The hostname of the windshaft server. Defaults to 127.0.0.1
    - map.windshaft.port: The port for the windshaft server. Defaults to 4000
    - winsdhaft_database: The database name to pass to the windshaft server. Defaults
        to the database name from the datastore URL.
    """

    standard_mss = """
                    #{resource_id} {{
                      marker-fill: #ee0000;
                      marker-opacity: 1;
                      marker-width: 8;
                      marker-line-color: white;
                      marker-line-width: 1;
                      marker-line-opacity: 0.9;
                      marker-placement: point;
                      marker-type: ellipse;
                      marker-allow-overlap: true;
                    }}
                    """

    gridded_mss = """
                  @color: #f02323;
                  @color1: spin(@color, 80);
                  @color2: spin(@color, 70);
                  @color3: spin(@color, 60);
                  @color4: spin(@color, 50);
                  @color5: spin(@color, 40);
                  @color6: spin(@color, 30);
                  @color7: spin(@color, 20);
                  @color8: spin(@color, 10);
                  @color9: spin(@color, 0);

                  #{resource_id} {{
                    marker-fill: @color1;
                    marker-opacity: 1;
                    marker-width: 7;
                    marker-placement: point;
                    marker-type: ellipse;
                    marker-line-width: 1.0;
                    marker-line-color: white;
                    marker-allow-overlap: true;
                    [count > 5] {{ marker-fill: @color2; }}
                    [count > 10] {{ marker-fill: @color3; }}
                    [count > 15] {{ marker-fill: @color4; }}
                    [count > 20] {{ marker-fill: @color5; }}
                    [count > 25] {{ marker-fill: @color6; }}
                    [count > 30] {{ marker-fill: @color7; }}
                    [count > 35] {{ marker-fill: @color8; }}
                    [count > 40] {{ marker-fill: @color9; }}
                  }}
                  """

    heatmap_mss = """
                  @size: 20;
                  #{resource_id}[zoom >= 4] {{
                    marker-file: url('symbols/marker.svg');
                    marker-allow-overlap: true;
                    marker-opacity: 0.2;
                    marker-width: @size;
                    marker-height: @size;
                    marker-clip: false;
                    image-filters: colorize-alpha(blue, cyan, green, yellow , orange, red);
                    opacity: 0.8;
                    [zoom >= 7] {{
                      marker-width: @size * 2;
                      marker-height: @size * 2;
                    }}
                  }}
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

    def __before__(self, action, **params):
        """Setup the request

        This will return a 500 error if there are missing configuration items, and a 400
        error if the resource_id parameter is missing.
        """
        super(MapController, self).__before__(action, **params)
        try:
            self.engine = create_engine(config['ckan.datastore.write_url'])
        except KeyError:
            base.abort(500, _("Missing configuration options"))

        self.windshaft_host = config.get('map.windshaft.host', '127.0.0.1')
        self.windshaft_port = config.get('map.windshaft.port', '4000')
        self.windshaft_database = config.get('map.windshaft.database', None) or self.engine.url.database

        if not request.params.get('resource_id'):
            base.abort(400, _("Missing resource id"))

        self.resource_id = request.params.get('resource_id')
        try:
            logic.get_action('resource_show')(None, {'id': self.resource_id})
        except logic.NotFound:
            base.abort(404, _('Resource not found'))
        except logic.NotAuthorized:
            base.abort(401, _('Unauthorized to read resources'))

    def _base_url(self):
        """Return the base Windshaft URL that will serve the tiles and grids.

        @rtype: str
        @return: The base windshaft URL that will serve the tile/overlay. The URL
            contains three placeholders: {x}, {y}, and {z} used to specify the required
            tile.
        """
        return 'http://{}:{}/database/{}/table/{}/{{z}}/{{x}}/{{y}}'.format(
            self.windshaft_host,
            self.windshaft_port,
            self.windshaft_database,
            self.resource_id
        )

    def _tile_url(self):
        """Return the tile Windshaft URL.

        @rtype: str
        @return: The Winsdhaft URL that will serve a tile The URL contains
            6 place holders: {x}, {y}, {z}, {sql} and {style}. See base_url
        """
        return self._base_url() + '.png?sql={sql}&style={style}'

    def _grid_url(self):
        """Return the grid windshaft URL.

        @rtype: str
        @return: The Windshaft URL that will serve a grid. The URL contains
            6 place holders: {x}, {y}, {z}, {cb} and {sql}
        """
        return self._base_url() + '.grid.json?callback={cb}&sql={sql}'

    def _geo_table(self):
        """Return the table used to build the Windshaft query

        @rtype: Table
        @return: Return the SQLAlchemy table corresponding to the geo table in Windshaft
        """
        metadata = MetaData()
        table = Table(self.resource_id, metadata, autoload=True, autoload_with=self.engine)
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

        geo_table = self._geo_table()

        width = helpers.MapnikPlaceholderColumn('pixel_width')
        height = helpers.MapnikPlaceholderColumn('pixel_height')

        # If we're drawing dots, then we can ignore the ones with identical positions by
        # selecting DISTINCT ON (the_geom_webmercator), but we need keep them for heatmaps
        # to get the right effect.
        # This provides a performance improvement for datasets with many points that share identical
        # positions. Note that there's an overhead to doing so for small datasets, and also that
        # it only has an effect for records with *identical* geometries.
        if style == 'heatmap':
            sub = select(geo_table.c.the_geom_webmercator.label('the_geom_webmercator'))
        elif style == 'gridded':
            sub = select([func.count(geo_table.c.the_geom_webmercator).label('count'),
                          func.ST_SnapToGrid(geo_table.c.the_geom_webmercator, width * 8, height * 8).label(
                              'the_geom_webmercator')])
        else:
            sub = select([geo_table.c.the_geom_webmercator.label('the_geom_webmercator')],
                         distinct='the_geom_webmercator',
                         from_obj=geo_table)

        if filters:
            for input_filters in json.loads(filters):
                # TODO - other types of filters
                if input_filters['type'] == 'term':
                    sub = sub.where(geo_table.c[input_filters['field']] == input_filters['term'])

        if geom:
            sub = sub.where(
                geo_functions.intersects(geo_table.c.the_geom_webmercator, geo_functions.transform(geom, 3857))
            )

        if style == 'heatmap':
            # no need to shuffle (see below), so use the subquery directly
            sql = helpers.interpolateQuery(sub, self.engine)
        elif style == 'gridded':
            sub = sub.where(func.ST_Intersects(geo_table.c.the_geom_webmercator,
                                               func.ST_SetSrid(helpers.MapnikPlaceholderColumn('bbox'), 3857)))

            # The group by needs to match the column chosen above, including by the size of the grid
            sub = sub.group_by(func.ST_SnapToGrid(geo_table.c.the_geom_webmercator, width * 8, height * 8))
            sub = sub.order_by(desc('count')).alias('sub')

            outer = select(['count', 'the_geom_webmercator']).select_from(sub).order_by(func.random())
            sql = helpers.interpolateQuery(outer, self.engine)
        else:
            # The SELECT ... DISTINCT ON query silently orders the results by lat and lon which leads to a nasty
            # overlapping effect when rendered. To avoid this, we shuffle the points in an outer
            # query.

            sub = sub.alias('sub')
            outer = select(['the_geom_webmercator']).select_from(sub).order_by(func.random())
            sql = helpers.interpolateQuery(outer, self.engine)

        if style == 'heatmap':
            mss = self.heatmap_mss.format(resource_id=resource_id)
        elif style == 'gridded':
            mss = self.gridded_mss.format(resource_id=resource_id)
        else:
            mss = self.standard_mss.format(resource_id=resource_id)

        url = self._tile_url().format(z=z, x=x, y=y, sql=sql, style=urllib.quote_plus(mss))
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
        sub_cols = [func.array_agg(geo_table.c.scientific_name).label('names'),
                    func.array_agg(geo_table.c['_id']).label('ids'),
                    func.array_agg(geo_table.c.species).label('species'),
                    func.count(geo_table.c.the_geom_webmercator).label('count'),
                    func.ST_SnapToGrid(geo_table.c.the_geom_webmercator, width * grid_size, height * grid_size).label(
                        'center')]

        # Filter the records by department, using any filters, and by the geometry drawn
        sub = select(sub_cols)

        if filters:
            for filter in json.loads(filters):
                # TODO - other types of filters
                if filter['type'] == 'term':
                    sub = sub.where(geo_table.c[filter['field']] == filter['term'])

        if geom:
            sub = sub.where(
                geo_functions.intersects(geo_table.c.the_geom_webmercator, geo_functions.transform(geom, 3857))
            )

        # We need to also filter the records to those in the area that we're looking at, otherwise the query causes
        # every record in the database to be snapped to the grid. Mapnik can fill in the !bbox! token for us, which
        # saves us trying to figure it out from the z/x/y numbers here.
        sub = sub.where(func.ST_Intersects(geo_table.c.the_geom_webmercator,
                                           func.ST_SetSrid(helpers.MapnikPlaceholderColumn('bbox'), 3857)))

        # The group by needs to match the column chosen above, including by the size of the grid
        sub = sub.group_by(func.ST_SnapToGrid(geo_table.c.the_geom_webmercator, width * grid_size, height * grid_size))
        sub = sub.order_by(desc('count')).alias('sub')

        # In the outer query we can use the overlapping records count and the location, but we also need to pop the
        # first record off of the array. If we were to return e.g. all the overlapping names, the json grids would
        # unbounded in size.

        # Note that the c.foo[1] syntax needs SQLAlchemy >= 0.8
        # However, geoalchemy breaks on SQLAlchemy >= 0.9, so be careful.
        outer_cols = [Column('names', ARRAY(String))[1].label('scientific_name'),
                      Column('ids', ARRAY(String))[1].label('_id'),
                      Column('species', ARRAY(String))[1].label('species'),
                      Column('count', Integer),
                      Column('center', helpers.Geometry).label('the_geom_webmercator')]

        s = select(outer_cols).select_from(sub)
        sql = helpers.interpolateQuery(s, self.engine)

        url = self._grid_url().format(z=z, x=x, y=y, cb=callback, sql=sql)
        response.headers['Content-type'] = 'text/javascript'
        grid = cStringIO.StringIO(urllib.urlopen(url).read())
        return grid
