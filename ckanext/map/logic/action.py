from pylons import config
import sqlalchemy
from sqlalchemy import create_engine, func
from sqlalchemy.sql import select

import ckan.plugins.toolkit as toolkit


def create_geom_columns(context, data_dict):
    """Add geom column to the given resource, and optionally populate them

    @param context: Current context
    @param data_dict: Parameters:
      - resource_id: The resource for which to create geom columns; REQUIRED
      - lat_field: The existing latitude field in the column, optional unless populate is true
      - long_field: The existing longitude field in the column, optional unless populate is true
      - populate: If true then pre-populate the geom fields using the latitude
                  and longitude fields. Defaults to true.
      - geom_field: The name of the 3587 geom field to create. Defaults to the one defined by
                    config. Only override if you know what you are doing.
      - geom_field_4326: The name of the 4326 geom field to create. Defaults to the one defined by
                          config. Only override if you know what you are doing.
    """
    # Read parameters
    resource_id = data_dict['resource_id']
    if 'geom_field' in data_dict:
        geom_field = data_dict['geom_field']
    else:
        geom_field = config.get('map.geom_field', '_the_geom_webmercator')
    if 'geom_field_4326' in data_dict:
        geom_field_4326 = data_dict['geom_field_4326']
    else:
        geom_field_4326 = config.get('map.geom_field_4326', '_geom')
    if 'populate' in data_dict:
        populate = data_dict['populate']
    else:
        populate = True

    # Add the two geometry columns - one in degrees (EPSG:4326) and one in spherical mercator metres (EPSG:3857)
    # the_geom_webmercator is used for windshaft
    engine = create_engine(config['ckan.datastore.write_url'])
    with engine.begin() as connection:
        s = select([func.AddGeometryColumn('public', resource_id, geom_field_4326, 4326, 'POINT', 2)])
        connection.execute(s)
        s = select([func.AddGeometryColumn('public', resource_id, geom_field, 3857, 'POINT', 2)])
        connection.execute(s)

    if populate:
        ugc = toolkit.get_action('update_geom_columns')
        ugc(context, data_dict)


def update_geom_columns(context, data_dict):
    """Repopulate the given geom columns

    @param context: Current context
    @param data_dict: Paramters:
      - resource_id: The resource to populate; REQUIRED
      - lat_field: The existing latitude field in the column, REQUIRED
      - long_field: The existing longitude field in the column, REQUIRED
      - geom_field: The name of the 3587 geom field to create. Defaults to the one defined by
                    config. Only override if you know what you are doing.
      - geom_field_4326: The name of the 4326 geom field to create. Defaults to the one defined by
                          config. Only override if you know what you are doing.
    """
    # Read parameters
    resource_id = data_dict['resource_id']
    lat_field = data_dict['lat_field']
    long_field = data_dict['long_field']
    if 'geom_field' in data_dict:
        geom_field = data_dict['geom_field']
    else:
        geom_field = config.get('map.geom_field', '_the_geom_webmercator')
    if 'geom_field_4326' in data_dict:
        geom_field_4326 = data_dict['geom_field_4326']
    else:
        geom_field_4326 = config.get('map.geom_field_4326', '_geom')

    # Create geometries from the latitude and longitude columns.
    engine = create_engine(config['ckan.datastore.write_url'])
    # TODO: change to sqlalchemy so we don't have to worry about escaping column names!
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