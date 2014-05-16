import sqlalchemy
from sqlalchemy import func
from sqlalchemy.sql import select, table
from sqlalchemy.exc import ProgrammingError

import ckan.plugins.toolkit as toolkit
from ckan.logic.action.create import resource_view_create as ckan_resource_view_create
from ckan.logic.action.delete import resource_view_delete as ckan_resource_view_delete
from ckan.logic.action.update import resource_view_update as ckan_resource_view_update

from ckanext.tiledmap.db import _get_engine
from ckanext.tiledmap.config import config


def has_geom_column(context, data_dict):
    """Returns TRUE if the given resource already has geom columns

    @param context: Current context
    @param data_dict: Parameters:
      - resource_id: The resource to check. REQUIRED.
    """
    geom_field = config['tiledmap.geom_field']
    geom_field_4326 = config['tiledmap.geom_field_4326']

    engine = _get_engine()
    found = False
    with engine.begin() as connection:
        t = table(data_dict['resource_id'])
        s = select('*', from_obj=t).limit(0)
        fields = connection.execute(s).keys()
        found = found or ((geom_field in fields) and (geom_field_4326 in fields))
    return found


def create_geom_columns(context, data_dict):
    """Add geom column to the given resource, and optionally populate them

    @param context: Current context
    @param data_dict: Parameters:
      - resource_id: The resource for which to create geom columns; REQUIRED
      - latitude_field: The existing latitude field in the column, optional unless populate is true
      - longitude_field: The existing longitude field in the column, optional unless populate is true
      - populate: If true then pre-populate the geom fields using the latitude
                  and longitude fields. Defaults to true.
    """
    # Read parameters
    resource_id = data_dict['resource_id']
    geom_field = config['tiledmap.geom_field']
    geom_field_4326 = config['tiledmap.geom_field_4326']
    if 'populate' in data_dict:
        populate = data_dict['populate']
    else:
        populate = True

    # Add the two geometry columns - one in degrees (EPSG:4326) and one in spherical mercator metres (EPSG:3857)
    # the_geom_webmercator is used for windshaft. Also create a spatial index on the geom (mercator) field.
    # TODO: should the index be optional/configurable?
    engine = _get_engine(write=True)
    with engine.begin() as connection:
        s = select([func.AddGeometryColumn('public', resource_id, geom_field_4326, 4326, 'POINT', 2)])
        connection.execute(s)
        s = select([func.AddGeometryColumn('public', resource_id, geom_field, 3857, 'POINT', 2)])
        connection.execute(s)
        s = sqlalchemy.text("""
          CREATE INDEX "{geom_field}_index"
              ON "{resource_id}"
           USING GIST("{geom_field}")
           WHERE "{geom_field}" IS NOT NULL;
        """.format(
            resource_id=resource_id,
            geom_field=geom_field
        ))
        connection.execute(s)

    if populate:
        ugc = toolkit.get_action('update_geom_columns')
        ugc(context, data_dict)


def update_geom_columns(context, data_dict):
    """Repopulate the given geom columns

    @param context: Current context
    @param data_dict: Paramters:
      - resource_id: The resource to populate; REQUIRED
      - latitude_field: The existing latitude field in the column, REQUIRED
      - longitude_field: The existing longitude field in the column, REQUIRED
    """
    # Read parameters
    resource_id = data_dict['resource_id']
    lat_field = data_dict['latitude_field']
    long_field = data_dict['longitude_field']
    geom_field = config['tiledmap.geom_field']
    geom_field_4326 = config['tiledmap.geom_field_4326']

    # Create geometries from the latitude and longitude columns.
    engine = _get_engine(write=True)
    # TODO: change to sqlalchemy so we don't have to worry about escaping column names!
    # TODO: should the ANALYZE be optional/configurable?
    with engine.begin() as connection:
        s = sqlalchemy.text("""
          UPDATE "{resource_id}"
          SET "{geom_field_4326}" = st_setsrid(st_makepoint("{long_field}"::float8, "{lat_field}"::float8), 4326)
          WHERE "{lat_field}" IS NOT NULL
        """.format(
            resource_id=resource_id,
            geom_field_4326=geom_field_4326,
            long_field=long_field,
            lat_field=lat_field
        ))
        connection.execute(s)
        s = sqlalchemy.text("""
          UPDATE "{resource_id}"
          SET "{geom_field}" = st_transform("{geom_field_4326}", 3857)
          WHERE st_y("{geom_field_4326}") <= 90 AND st_y("{geom_field_4326}") >= -90
        """.format(
            resource_id=resource_id,
            geom_field=geom_field,
            geom_field_4326=geom_field_4326
        ))
        connection.execute(s)
        s = sqlalchemy.text("""
          ANALYZE "{resource_id}"
        """.format(
            resource_id=resource_id
        ))
        connection.execute(s)


def resource_view_create(context, data_dict):
    """Override ckan's resource_view_create so we can create geom fields when new tiled map views are added"""
    # Invoke ckan resource_view_create
    r = ckan_resource_view_create(context, data_dict)
    # If this was a tiled map view, create our geom fields
    if data_dict['view_type'] == 'tiledmap':
        if not has_geom_column(context, data_dict):
            create_geom_columns(context, data_dict)
        else:
            try:
                update_geom_columns(context, data_dict)
            except ProgrammingError:
                # TODO: we cannot run this on materialized views.
                pass
    return r


def resource_view_update(context, data_dict):
    # Invoke ckan resource_view_update
    r = ckan_resource_view_update(context, data_dict)
    # If this was a tiled map view, update values in our geom fields
    if r['view_type'] == 'tiledmap':
        if not has_geom_column(context, data_dict):
            create_geom_columns(context, data_dict)
        else:
            try:
                update_geom_columns(context, data_dict)
            except ProgrammingError:
                # TODO We cannot run this on materialized views.
                pass
    return r


def resource_view_delete(context, data_dict):
    # TODO: We need to check if there any other tiled map view on the given resource. If not, we can drop the fields.
    r = ckan_resource_view_delete(context, data_dict)
    return r