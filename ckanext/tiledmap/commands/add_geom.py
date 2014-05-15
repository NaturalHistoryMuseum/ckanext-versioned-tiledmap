import re
import ckan.model as model
import ckan.plugins.toolkit as toolkit
import ckan.lib.cli as cli

import ConfigParser

import sqlalchemy
import pylons
import logging

from sqlalchemy.sql import select
from sqlalchemy import func

# Notes:
# Before running this you need to run the following:
# sudo apt-get install postgresql-contrib-9.1 postgresql-9.1-postgis
# psql -d datastore_default -f /usr/share/postgresql/9.1/contrib/postgis-1.5/postgis.sql
# psql -d datastore_default -c "ALTER TABLE geometry_columns OWNER TO ckan_default"
# psql -d datastore_default -c "ALTER TABLE spatial_ref_sys OWNER TO ckan_default"
# psql -d datastore_default -f /usr/share/postgresql/9.1/contrib/postgis-1.5/spatial_ref_sys.sql

log = logging.getLogger('ckan')

class AddGeomCommand(cli.CkanCommand):
    '''
    Commands:
        paster ckanextmap add-all-geoms -c /etc/ckan/default/development.ini

    Where:
        <config> = path to your ckan config file

    The commands should be run from the ckanext-map directory.
    '''

    summary = __doc__.split('\n')[0]
    usage = __doc__
    counter = 0

    def command(self):
        '''
        Parse command line arguments and call appropriate method.
        '''
        if not self.args or self.args[0] in ['--help', '-h', 'help']:
            print AddGeomCommand.__doc__
            return

        cmd = self.args[0]

        self.method = cmd.replace('-', '_')

        ## Need to call _load_config() before running
        self._load_config()

        if self.method.startswith('_'):
            log.error('Cannot call private command %s' % (self.method,))
            return

        # Set up API context
        user = toolkit.get_action('get_site_user')({'model': model, 'ignore_auth': True}, {})
        self.context = {'model': model, 'session': model.Session, 'user': user['name'], 'extras_as_string': True}

        ## Set up datastore DB engine
        self.datastore_db_engine = sqlalchemy.create_engine(pylons.config['ckan.datastore.write_url'])


        # Try and call the method, if it exists
        if hasattr(self, self.method):
            getattr(self, self.method)()
        else:
            log.error('Command %s not recognized' % (self.method,))

    def add_all_geoms(self):
        packages = toolkit.get_action('current_package_list_with_resources')(self.context, {})
        for package in packages:
          for resource in package['resources']:
            log.info(resource['id'])

            has_col = False
            inspector = sqlalchemy.inspect(self.datastore_db_engine)
            cols = inspector.get_columns(resource['id'])
            for col in cols:
              if col['name'] == 'latitude':
                has_col = True

            log.info('Has latitude column: ' + str(has_col))

            if has_col:
              # We need to wrap things in a transaction, since SQLAlchemy thinks that all selects (including AddGeometryColumn)
              # should be rolled back when the connection terminates.
              connection = self.datastore_db_engine.connect()
              trans = connection.begin()

              # Use these to remove the columns, if you're doing development things
              #connection.execute(sqlalchemy.text("select DropGeometryColumn('" + resource['id'] + "', 'geom')"))
              #connection.execute(sqlalchemy.text("select DropGeometryColumn('" + resource['id'] + "', 'the_geom_webmercator')"))

              # Add the two geometry columns - one in degrees (EPSG:4326) and one in spherical mercator metres (EPSG:3857)
              # the_geom_webmercator is used for windshaft
              s = select([func.AddGeometryColumn('public', resource['id'], 'geom', 4326, 'POINT', 2)])
              connection.execute(s)
              s = select([func.AddGeometryColumn('public', resource['id'], 'the_geom_webmercator', 3857, 'POINT', 2)])
              connection.execute(s)

              # Create geometries from the latitude and longitude columns. Note the bits and pieces of data cleaning that are required!
              # This could, in theory, be converted to SQLAlchemy commands but ELIFEISTOOSHORT
              s = sqlalchemy.text("update \"" + resource['id'] + "\" set geom = st_setsrid(st_makepoint(longitude::float8, latitude::float8), 4326) where latitude is not null and latitude != '' and latitude not like '%{%'")
              connection.execute(s)
              s = sqlalchemy.text("update \"" + resource['id'] + "\" set the_geom_webmercator = st_transform(geom, 3857) where y(geom) < 90 and y(geom) > -90")
              connection.execute(s)

              trans.commit()

