from pylons import config
import ckan.logic as logic
import ckan.lib.base as base
import ckan.model as model
import ckan.plugins as p
from ckan.common import OrderedDict, _, json, request, c, g, response
from ckan.lib.jsonp import jsonpify
import logging

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

    def tile(self):

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

        return 'TILE'




