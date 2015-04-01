from sqlalchemy.exc import ProgrammingError, DataError, InternalError

from ckan.common import _
from ckan.lib.helpers import flash_error, flash_success
from ckan.logic.action.create import resource_view_create as ckan_resource_view_create
from ckan.logic.action.delete import resource_view_delete as ckan_resource_view_delete
from ckan.logic.action.update import resource_view_update as ckan_resource_view_update
from ckanext.dataspatial.lib.postgis import has_postgis_columns, create_postgis_columns, populate_postgis_columns

def resource_view_create(context, data_dict):
    """Override ckan's resource_view_create so we can create geom fields when new tiled map views are added"""
    # Invoke ckan resource_view_create
    r = ckan_resource_view_create(context, data_dict)
    if r['view_type'] == 'tiledmap':
        _create_update_resource(r, context, data_dict)
    return r


def resource_view_update(context, data_dict):
    """Override ckan's resource_view_update so we can update geom fields when the tiled map view is edited"""
    # Invoke ckan resource_view_update
    r = ckan_resource_view_update(context, data_dict)
    if r['view_type'] == 'tiledmap':
        _create_update_resource(r, context, data_dict)
    return r


def resource_view_delete(context, data_dict):
    # TODO: We need to check if there any other tiled map view on the given resource. If not, we can drop the fields.
    r = ckan_resource_view_delete(context, data_dict)
    return r

def _create_update_resource(r, context, data_dict):
    """Create/update geom field on the given resource"""
    options = dict(data_dict.items() + {'populate': False}.items())
    if not has_postgis_columns(data_dict['resource_id']):
        try:
             create_postgis_columns(data_dict['resource_id'])
        except ProgrammingError as e:
            flash_error(_('The extension failed to initialze the database table to support geometries. You will' +
            ' not be able to use this view. Please inform an administrator.'))
            return
    try:
        populate_postgis_columns(
            data_dict['resource_id'],
            data_dict['latitude_field'],
            data_dict['longitude_field']
        )
    except (DataError, InternalError) as e:
        flash_error(_('It was not possible to create the geometry data from the given latitude/longitude columns.' +
        'Those columns must contain only decimal numbers, with latitude between -90 and +90 and longitude ' +
        'between -180 and +180. Please correct the data or select different fields.'))
    else:
        flash_success(_('Successfully created the geometric data.'))
