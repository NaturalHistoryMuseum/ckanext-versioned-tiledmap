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

    def tile(self, z, x, y):

        """
        View a map tile
        :return: string
        """

        # URL in the format http://10.11.12.13:5000/map-tile?resource_id=64351390-720f-4702-bd25-9fa607629b3f

        resource_id = request.params.get('resource_id')

        context = {'model': model, 'session': model.Session, 'user': c.user or c.author}

        # Try & get the resource
        try:
            c.resource = get_action('resource_show')(context, {'id': resource_id})
        except NotFound:
            abort(404, _('Resource not found'))
        except NotAuthorized:
            abort(401, _('Unauthorized to read resources'))

        url = _('http://10.11.12.1:4000/database/nhm_botany/table/botany_all/{z}/{x}/{y}.png').format(z=z,x=x,y=y)
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
        sql = request.params.get('sql')

        context = {'model': model, 'session': model.Session, 'user': c.user or c.author}

        # Try & get the resource
        try:
            c.resource = get_action('resource_show')(context, {'id': resource_id})
        except NotFound:
            abort(404, _('Resource not found'))
        except NotAuthorized:
            abort(401, _('Unauthorized to read resources'))

        url = _('http://10.11.12.1:4000/database/nhm_botany/table/botany_all/{z}/{x}/{y}.grid.json?callback={cb}&sql={sql}').format(z=z,x=x,y=y,cb=callback,sql=sql)
        response.headers['Content-type'] = 'text/javascript'
        grid =  cStringIO.StringIO(urllib.urlopen(url).read())
        return grid


