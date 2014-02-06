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
    Controlled for displaying map tiles
    """

    def botany_table(self):
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
        heatmap = request.params.get('heatmap')

        context = {'model': model, 'session': model.Session, 'user': c.user or c.author}

        # Try & get the resource
        try:
            c.resource = get_action('resource_show')(context, {'id': resource_id})
        except NotFound:
            abort(404, _('Resource not found'))
        except NotAuthorized:
            abort(401, _('Unauthorized to read resources'))

        engine = create_engine('postgresql://')

        botany_all = self.botany_table()

        dep = 'Botany' # TODO: depends on resource

        s = select([botany_all]).where(botany_all.c.collection_department==dep)

        if filters:
          for filter in json.loads(filters):
            # TODO - other types of filters
            if (filter['type'] == 'term'):
              s = s.where(botany_all.c[filter['field']]==filter['term'])

        if geom:
          s = s.where(geoFunctions.intersects(botany_all.c.the_geom_webmercator,geoFunctions.transform(geom,3857)))

        sql = helpers.interpolateQuery(s, engine)

        style = ''

        if heatmap:
          style = urllib.quote_plus("@size: 20;  #botany_all[zoom >= 4] {   marker-file: url('http://thunderflames.org/temp/marker.svg');   marker-allow-overlap: true;   marker-opacity: 0.2;   marker-width: @size;   marker-height: @size;   marker-clip: false;   image-filters: colorize-alpha(blue, cyan, green, yellow , orange, red);   opacity: 0.8;   [zoom >= 7] {     marker-width: @size * 2;     marker-height: @size * 2;   } }")

        url = _('http://10.11.12.1:4000/database/nhm_botany/table/botany_all/{z}/{x}/{y}.png?sql={sql}&style={style}').format(z=z,x=x,y=y,sql=sql,style=style)
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

        context = {'model': model, 'session': model.Session, 'user': c.user or c.author}

        # Try & get the resource
        try:
            c.resource = get_action('resource_show')(context, {'id': resource_id})
        except NotFound:
            abort(404, _('Resource not found'))
        except NotAuthorized:
            abort(401, _('Unauthorized to read resources'))

        engine = create_engine('postgresql://')

        botany_all = self.botany_table()

        sub_cols = [func.array_agg(botany_all.c.scientific_name).label('names'),
                    func.array_agg(botany_all.c['_id']).label('ids'),
                    func.array_agg(botany_all.c.species).label('species'),
                    func.count(botany_all.c.the_geom_webmercator).label('count'),
                    func.ST_SnapToGrid(botany_all.c.the_geom_webmercator, 1000, 1000).label('center')
                   ]

        dep = 'Botany' # TODO: depends on resource

        sub = select(sub_cols).where(botany_all.c.collection_department==dep)
        if filters:
          for filter in json.loads(filters):
            # TODO - other types of filters
            if (filter['type'] == 'term'):
              sub = sub.where(botany_all.c[filter['field']]==filter['term'])
        sub = sub.where(func.ST_Intersects(botany_all.c.the_geom_webmercator, func.ST_SetSrid(helpers.MapnikPlaceholderColumn('bbox'), 3857)))
        sub = sub.group_by(func.ST_SnapToGrid(botany_all.c.the_geom_webmercator,1000,1000))
        sub = sub.order_by(desc('count')).alias('sub')
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

        url = _('http://10.11.12.1:4000/database/nhm_botany/table/botany_all/{z}/{x}/{y}.grid.json?callback={cb}&sql={sql}').format(z=z,x=x,y=y,cb=callback,sql=sql)
        response.headers['Content-type'] = 'text/javascript'
        grid =  cStringIO.StringIO(urllib.urlopen(url).read())
        return grid


