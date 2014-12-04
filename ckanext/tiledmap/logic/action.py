import sqlalchemy
from sqlalchemy import func
from sqlalchemy.sql import select, table
from sqlalchemy.exc import ProgrammingError, DataError, InternalError

from ckan.common import _
from ckan.lib.helpers import flash_error, flash_success
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
    latitude_field = data_dict['latitude_field']
    longitude_field = data_dict['longitude_field']
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
          CREATE INDEX "{resource_id}_{geom_field}_index"
              ON "{resource_id}"
           USING GIST("{geom_field}")
           WHERE "{geom_field}" IS NOT NULL;
        """.format(
            resource_id=resource_id,
            geom_field=geom_field
        ))
        connection.execute(s)

        # We also want to index the lat / long columns
        for field_name in [latitude_field, longitude_field]:
            s = sqlalchemy.text('CREATE INDEX ON "{resource_id}" ("{field_name}")'.format(
                resource_id=resource_id,
                field_name=field_name
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

    connection = engine.raw_connection()

    # This is timing out for big datasets (KE EMu), so we're going to break into a batch operation
    # We need two cursors, one for reading; one for writing
    # And the write cursor will be committed every x number of times (incremental_commit_size)
    read_cursor = connection.cursor()
    write_cursor = connection.cursor()

    # Retrieve all IDs of records that require updating
    # Either: lat field doesn't match that in the geom column
    # OR geom is  null and /lat/lon is populated



    read_sql = """
          SELECT _id
          FROM "{resource_id}"
          WHERE "{lat_field}" <= 90 AND "{lat_field}" >= -90 AND "{long_field}" <= 180 AND "{long_field}" >= -180
         """.format(
            resource_id=resource_id,
            geom_field=geom_field,
            geom_field_4326=geom_field_4326,
            long_field=long_field,
            lat_field=lat_field
        )

    read_cursor.execute(read_sql)

    count = 0
    incremental_commit_size = 1000

    sql = """
          UPDATE "{resource_id}"
          SET "{geom_field_4326}" = st_setsrid(st_makepoint("{long_field}"::float8, "{lat_field}"::float8), 4326),
              "{geom_field}" = st_transform(st_setsrid(st_makepoint("{long_field}"::float8, "{lat_field}"::float8), 4326), 3857)
          WHERE _id = %s
         """.format(
            resource_id=resource_id,
            geom_field=geom_field,
            geom_field_4326=geom_field_4326,
            long_field=long_field,
            lat_field=lat_field
        )

    while True:

        output = read_cursor.fetchmany(incremental_commit_size)

        if not output:
            break

        for row in output:
            write_cursor.execute(sql,([row[0]]))

        #commit, invoked every incremental commit size
        connection.commit()
        count = count + incremental_commit_size

        print '%s records updated' % count

    connection.commit()


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
    if not has_geom_column(context, options):
        try:
             create_geom_columns(context, options)
        except ProgrammingError as e:
            flash_error(_('The extension failed to initialze the database table to support geometries. You will' +
            ' not be able to use this view. Please inform an administrator.'))
            return
    try:
        update_geom_columns(context, options)
    except (DataError, InternalError) as e:
        flash_error(_('It was not possible to create the geometry data from the given latitude/longitude columns.' +
        'Those columns must contain only decimal numbers, with latitude between -90 and +90 and longitude ' +
        'between -180 and +180. Please correct the data or select different fields.'))
    else:
        flash_success(_('Successfully created the geometric data.'))