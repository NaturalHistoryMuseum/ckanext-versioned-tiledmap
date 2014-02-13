from pylons import config
import ckan.logic as logic
import ckan.lib.base as base
import ckan.model as model
import ckan.plugins as p
from ckan.common import OrderedDict, _, json, request, c, g, response
from ckan.lib.jsonp import jsonpify
import logging
import requests
import urllib
import cStringIO
import ckanext.map.lib.helpers as helpers
from sqlalchemy.sql import select
from sqlalchemy import Table, Column, Integer, String, MetaData
from sqlalchemy import create_engine
import geoalchemy.functions as geoFunctions
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import func
from sqlalchemy.sql import desc

log = logging.getLogger(__name__)

render = base.render
abort = base.abort
redirect = base.redirect

NotFound = logic.NotFound
NotAuthorized = logic.NotAuthorized
ValidationError = logic.ValidationError
get_action = logic.get_action

class MapController(base.BaseController):
    """
    Controller for displaying map tiles and grids
    """

    standard_mss =  """
                    #botany_all {
                      marker-fill: #ee0000;
                      marker-opacity: 1;
                      marker-width: 8;
                      marker-line-color: white;
                      marker-line-width: 1;
                      marker-line-opacity: 0.9;
                      marker-placement: point;
                      marker-type: ellipse;
                      marker-allow-overlap: true;
                    }
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

                  #botany_all {
                    marker-fill: @color1;
                    marker-opacity: 1;
                    marker-width: 7;
                    marker-placement: point;
                    marker-type: ellipse;
                    marker-line-width: 1.0;
                    marker-line-color: white;
                    marker-allow-overlap: true;
                    [count > 5] { marker-fill: @color2; }
                    [count > 10] { marker-fill: @color3; }
                    [count > 15] { marker-fill: @color4; }
                    [count > 20] { marker-fill: @color5; }
                    [count > 25] { marker-fill: @color6; }
                    [count > 30] { marker-fill: @color7; }
                    [count > 35] { marker-fill: @color8; }
                    [count > 40] { marker-fill: @color9; }
                  }
                  """

    heatmap_mss = """
                  @size: 20;
                  #botany_all[zoom >= 4] {
                    marker-file: url('symbols/marker.svg');
                    marker-allow-overlap: true;
                    marker-opacity: 0.2;
                    marker-width: @size;
                    marker-height: @size;
                    marker-clip: false;
                    image-filters: colorize-alpha(blue, cyan, green, yellow , orange, red);
                    opacity: 0.8;
                    [zoom >= 7] {
                      marker-width: @size * 2;
                      marker-height: @size * 2;
                    }
                  }
                  """

    windshaft_base = 'http://10.11.12.1:4000/database/nhm_botany/table/botany_all/{z}/{x}/{y}'

    def tile_url(self):
      return self.windshaft_base + '.png?sql={sql}&style={style}'

    def grid_url(self):
      return self.windshaft_base + '.grid.json?callback={cb}&sql={sql}'

    def geo_table(self):
      """ Return the SQLAlchemy table corresponding to the geo table in Windshaft

      Currently windshaft is configured with a slightly misleading table name of 'botany_all' containing
      all records, not just botany ones.
      """
      metadata = MetaData()
      table = Table('botany_all', metadata,
            Column('_id', Integer),
            Column('type', String),
            Column('collection_department', String),
            Column('collection_sub_department', String),
            Column('catalogue_number', String),
            Column('scientific_name', String),
            Column('genus', String),
            Column('subgenus', String),
            Column('species', String),
            Column('scientific_name_author', String),
            Column('continent', String),
            Column('country', String),
            Column('state_province', String),
            Column('county', String),
            Column('expedition_name', String),
            Column('vessel_name', String),
            Column('the_geom_webmercator', helpers.Geometry)
      )
      return table

    def tile(self, z, x, y):

        """
        View a map tile
        :return: png image
        """

        # URL in the format http://10.11.12.13:5000/map-tile/2/2/2.png?resource_id=64351390-720f-4702-bd25-9fa607629b3f

        resource_id = request.params.get('resource_id')
        filters = request.params.get('filters')
        query = request.params.get('q')
        geom = request.params.get('geom')
        style = request.params.get('style')

        context = {'model': model, 'session': model.Session, 'user': c.user or c.author}

        # Try & get the resource
        try:
            c.resource = get_action('resource_show')(context, {'id': resource_id})
        except NotFound:
            abort(404, _('Resource not found'))
        except NotAuthorized:
            abort(401, _('Unauthorized to read resources'))

        engine = create_engine('postgresql://')

        geo_table = self.geo_table()

        dep = c.resource['name']

        width = helpers.MapnikPlaceholderColumn('pixel_width')
        height = helpers.MapnikPlaceholderColumn('pixel_height')

        # If we're drawing dots, then we can ignore the ones with identical positions by
        # selecting DISTINCT ON (the_geom_webmercator), but we need keep them for heatmaps
        # to get the right effect.
        # This provides a performance improvement for datasets with many points that share identical
        # positions. Note that there's an overhead to doing so for small datasets, and also that
        # it only has an effect for records with *identical* geometries.
        if style == 'heatmap':
          sub = select(['the_geom_webmercator'])
        elif style == 'gridded':
          sub = select([func.count(geo_table.c.the_geom_webmercator).label('count'),func.ST_SnapToGrid(geo_table.c.the_geom_webmercator, width * 8, height * 8).label('the_geom_webmercator')])
        else:
          sub = select(['the_geom_webmercator'], distinct='the_geom_webmercator')

        sub = sub.where(geo_table.c.collection_department==dep)

        if filters:
          for filter in json.loads(filters):
            # TODO - other types of filters
            if (filter['type'] == 'term'):
              sub = sub.where(geo_table.c[filter['field']]==filter['term'])

        if geom:
          sub = sub.where(geoFunctions.intersects(geo_table.c.the_geom_webmercator,geoFunctions.transform(geom,3857)))

        if style == 'heatmap':
          # no need to shuffle (see below), so use the subquery directly
          sql = helpers.interpolateQuery(sub, engine)
        elif style == 'gridded':
          sub = sub.where(func.ST_Intersects(geo_table.c.the_geom_webmercator, func.ST_SetSrid(helpers.MapnikPlaceholderColumn('bbox'), 3857)))

          # The group by needs to match the column chosen above, including by the size of the grid
          sub = sub.group_by(func.ST_SnapToGrid(geo_table.c.the_geom_webmercator,width * 8,height * 8))
          sub = sub.order_by(desc('count')).alias('sub')

          outer = select(['count', 'the_geom_webmercator']).select_from(sub).order_by(func.random())
          sql = helpers.interpolateQuery(outer, engine)
        else:
          # The SELECT ... DISTINCT ON query silently orders the results by lat and lon which leads to a nasty
          # overlapping effect when rendered. To avoid this, we shuffle the points in an outer
          # query.

          sub = sub.alias('sub')
          outer = select(['the_geom_webmercator']).select_from(sub).order_by(func.random())
          sql = helpers.interpolateQuery(outer, engine)

        if style == 'heatmap':
          mss = self.heatmap_mss
        elif style == 'gridded':
          mss = self.gridded_mss
        else:
          mss = self.standard_mss

        url = self.tile_url().format(z=z,x=x,y=y,sql=sql,style=urllib.quote_plus(mss))
        response.headers['Content-type'] = 'image/png'
        tile =  cStringIO.StringIO(urllib.urlopen(url).read())
        return tile

    def grid(self, z, x, y):

        """
        View a utfgrid
        :return: string
        """

        # URL in the format http://10.11.12.13:5000/map-grid/2/2/2.grid.json?resource_id=64351390-720f-4702-bd25-9fa607629b3f

        resource_id = request.params.get('resource_id')
        callback = request.params.get('callback')
        filters = request.params.get('filters')
        query = request.params.get('q')
        geom = request.params.get('geom')
        style = request.params.get('style')

        context = {'model': model, 'session': model.Session, 'user': c.user or c.author}

        # Try & get the resource
        try:
            c.resource = get_action('resource_show')(context, {'id': resource_id})
        except NotFound:
            abort(404, _('Resource not found'))
        except NotAuthorized:
            abort(401, _('Unauthorized to read resources'))

        engine = create_engine('postgresql://')

        geo_table = self.geo_table()

        if style == 'gridded':
          grid_size = 8
        else:
          grid_size = 4

        # Set mapnik placeholders for the size of each pixel. Allows the grid to adjust automatically to the pixel size
        # at whichever zoom we happen to be at.
        width = helpers.MapnikPlaceholderColumn('pixel_width')
        height = helpers.MapnikPlaceholderColumn('pixel_height')

        # To calculate the number of overlapping points, we first snap them to a grid roughly four pixels wide, and then
        # group them by that grid. This allows us to count the records, but we need to aggregate the rest of the information
        # in order to later return the "top" record from the stack of overlapping records
        sub_cols = [func.array_agg(geo_table.c.scientific_name).label('names'),
                    func.array_agg(geo_table.c['_id']).label('ids'),
                    func.array_agg(geo_table.c.species).label('species'),
                    func.count(geo_table.c.the_geom_webmercator).label('count'),
                    func.ST_SnapToGrid(geo_table.c.the_geom_webmercator, width * grid_size, height * grid_size).label('center')
                   ]

        # Filter the records by department, using any filters, and by the geometry drawn
        dep = c.resource['name']
        sub = select(sub_cols).where(geo_table.c.collection_department==dep)

        if filters:
          for filter in json.loads(filters):
            # TODO - other types of filters
            if (filter['type'] == 'term'):
              sub = sub.where(geo_table.c[filter['field']]==filter['term'])

        if geom:
          sub = sub.where(geoFunctions.intersects(geo_table.c.the_geom_webmercator,geoFunctions.transform(geom,3857)))

        # We need to also filter the records to those in the area that we're looking at, otherwise the query causes every
        # record in the database to be snapped to the grid. Mapnik can fill in the !bbox! token for us, which saves us
        # trying to figure it out from the z/x/y numbers here.
        sub = sub.where(func.ST_Intersects(geo_table.c.the_geom_webmercator, func.ST_SetSrid(helpers.MapnikPlaceholderColumn('bbox'), 3857)))

        # The group by needs to match the column chosen above, including by the size of the grid
        sub = sub.group_by(func.ST_SnapToGrid(geo_table.c.the_geom_webmercator, width * grid_size, height * grid_size))
        sub = sub.order_by(desc('count')).alias('sub')

        # In the outer query we can use the overlapping records count and the location, but we also need to pop the first
        # record off of the array. If we were to return e.g. all the overlapping names, the json grids would unbounded in size.

        # Note that the c.foo[1] syntax needs SQLAlchemy >= 0.8
        # However, geoalchemy breaks on SQLAlchemy >= 0.9, so be careful.
        outer_cols = [Column('names', ARRAY(String))[1].label('scientific_name'),
                      Column('ids', ARRAY(String))[1].label('_id'),
                      Column('species', ARRAY(String))[1].label('species'),
                      Column('count', Integer),
                      Column('center', helpers.Geometry).label('the_geom_webmercator')
                    ]
        s = select(outer_cols).select_from(sub)
        sql = helpers.interpolateQuery(s, engine)

        url = self.grid_url().format(z=z,x=x,y=y,cb=callback,sql=sql)
        response.headers['Content-type'] = 'text/javascript'
        grid =  cStringIO.StringIO(urllib.urlopen(url).read())
        return grid
