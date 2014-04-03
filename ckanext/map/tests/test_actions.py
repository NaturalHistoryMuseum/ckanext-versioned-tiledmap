from pylons import config
import paste.fixture
import nose
from sqlalchemy import create_engine
from sqlalchemy.sql import select
from sqlalchemy import Table, MetaData, func

import ckan
import ckan.tests as tests
import ckan.plugins as p
import ckan.plugins.toolkit as toolkit
import ckan.config.middleware as middleware
import ckan.lib.create_test_data as ctd
from ckan.logic.action.create import package_create
from ckan.logic.action.delete import package_delete
from ckanext.datastore.logic.action import datastore_create, datastore_delete, datastore_upsert


class TestMapActions(tests.WsgiAppCase):
    """Test cases for the Map plugin actions"""
    context = None
    engine = None

    @classmethod
    def setup_class(cls):
        """Prepare the test"""
        # We need datastore for these tests.
        if not tests.is_datastore_supported():
            raise nose.SkipTest("Datastore not supported")

        # Setup a test app
        wsgiapp = middleware.make_app(config['global_conf'], **config)
        cls.app = paste.fixture.TestApp(wsgiapp)
        ctd.CreateTestData.create()
        cls.context = {'model': ckan.model,
                       'session': ckan.model.Session,
                       'user': ckan.model.User.get('testsysadmin').name}
        cls.engine = create_engine(config['ckan.datastore.write_url'])

        # Load plugins
        p.load('map')
        p.load('datastore')

    @classmethod
    def teardown_class(cls):
        """Clean up"""
        p.unload('map')
        p.unload('datastore')

    def setup(self):
        """Prepare each test"""
        # Setup a dummy datastore.
        self.dataset = package_create(TestMapActions.context, {'name': 'map-test-dataset'})
        self.resource = datastore_create(TestMapActions.context, {
            'resource': {
                'package_id': self.dataset['id']
            },
            'fields': [
                {'id': 'id', 'type': 'integer'},
                {'id': 'latitude', 'type': 'text'},
                {'id': 'longitude', 'type': 'text'},
                {'id': 'skip', 'type': 'text'},
                {'id': 'lat2', 'type': 'text'},
                {'id': 'long2', 'type': 'text'}
            ],
            'primary_key': 'id'
        })

        # Add some data.
        datastore_upsert(TestMapActions.context, {
            'resource_id': self.resource['resource_id'],
            'method': 'upsert',
            'records': [{
                            'id': 1,
                            'latitude': '-11',
                            'longitude': '-15',
                            'skip': 'no',
                            'lat2': '1',
                            'long2': '1'
                        }, {
                            'id': 2,
                            'latitude': '23',
                            'longitude': '48',
                            'skip': 'no',
                            'lat2': '2',
                            'long2': '2'
                        }, {
                            'id': 3,
                            'latitude': '',
                            'longitude': '',
                            'skip': 'yes',
                            'lat2': '',
                            'long2': ''
                        }, {
                            'id': 4,
                            'latitude': '1234',
                            'longitude': '1234',
                            'skip': 'yes',
                            'lat2': '',
                            'long2': ''
                        }, {
                            'id': 5,
                            'latitude': '{4,5}',
                            'longitude': '{6,7}',
                            'skip': 'yes',
                            'lat2': '',
                            'long2': ''
                        }]
        })

    def teardown(self):
        """Clean up after each test"""
        datastore_delete(TestMapActions.context, {'resource_id': self.resource['resource_id']})
        package_delete(TestMapActions.context, {'id': self.dataset['id']})
        tod = ['map.geom_field', 'map.geom_field_4326']
        for opt in tod:
            if config.get(opt, None) is not None:
                del config[opt]

    def test_create_geom_columns(self):
        """ Test creating geom columns using default settings."""
        # Create the geom columns
        create_geom_columns = toolkit.get_action('create_geom_columns')
        create_geom_columns(TestMapActions.context, {
            'resource_id': self.resource['resource_id'],
            'lat_field': 'latitude',
            'long_field': 'longitude'
        })
        # Test we have the expected columns
        metadata = MetaData()
        table = Table(self.resource['resource_id'], metadata, autoload=True, autoload_with=TestMapActions.engine)
        assert '_geom' in table.c, "Column geom was not created"
        assert '_the_geom_webmercator' in table.c, "Column _the_geom_webmercator was not created"
        s = select([
            table.c['latitude'],
            table.c['longitude'],
            func.st_x(table.c['_geom']).label('x'),
            func.st_y(table.c['_geom']).label('y'),
            table.c['skip']
        ]).where(table.c['_the_geom_webmercator'].isnot(None))
        r = TestMapActions.engine.execute(s)
        try:
            assert r.rowcount == 2, "Did not report the expected rows. Expecting {}, got {}".format(2, r.rowcount)
            for row in r:
                assert float(row['x']) == float(row['longitude']), "Longitude not correctly set"
                assert float(row['y']) == float(row['latitude']), "Latitude not correctly set"
                assert row['skip'] == 'no', "Row was included which should have not"
        except:
            raise
        finally:
            r.close()

    def test_create_geom_columns_settings(self):
        """Ensure settings are used if defined when creating columns"""
        config['map.geom_field'] = 'alt_geom_webmercator'
        config['map.geom_field_4326'] = 'alt_geom'
        # Test global settings override defaults
        create_geom_columns = toolkit.get_action('create_geom_columns')
        create_geom_columns(TestMapActions.context, {
            'resource_id': self.resource['resource_id'],
            'populate': False
        })
        # Test we have the expected columns
        metadata = MetaData()
        table = Table(self.resource['resource_id'], metadata, autoload=True, autoload_with=TestMapActions.engine)
        assert 'alt_geom' in table.c, "Column alt_geom was not created"
        assert 'alt_geom_webmercator' in table.c, "Column alt_geom_webmercator was not created"
        # Test passed in settings override global settings and defaults
        create_geom_columns(TestMapActions.context, {
            'resource_id': self.resource['resource_id'],
            'geom_field_4326': 'alt_geom_2',
            'geom_field': 'alt_geom_webmercator_2',
            'populate': False
        })
        # Test we have the expected columns
        metadata = MetaData()
        table = Table(self.resource['resource_id'], metadata, autoload=True, autoload_with=TestMapActions.engine)
        assert 'alt_geom_2' in table.c, "Column alt_geom_2 was not created"
        assert 'alt_geom_webmercator_2' in table.c, "Column alt_geom_webmercator_2 was not created"

    def test_populate(self):
        """Ensure it's possible to first create the columns and populate/update them later"""
        create_geom_columns = toolkit.get_action('create_geom_columns')
        create_geom_columns(TestMapActions.context, {
            'resource_id': self.resource['resource_id'],
            'populate': False
        })
        # Test the result did not populate the geom field
        metadata = MetaData()
        table = Table(self.resource['resource_id'], metadata, autoload=True, autoload_with=TestMapActions.engine)
        s = select(['*']).where(table.c['_the_geom_webmercator'].isnot(None))
        r = TestMapActions.engine.execute(s)
        try:
            assert r.rowcount == 0, "Table was populated"
        except:
            raise
        finally:
            r.close()

        # Now populate the entries, and test they are correct.
        update_geom_columns = toolkit.get_action('update_geom_columns')
        update_geom_columns(TestMapActions.context, {
            'resource_id': self.resource['resource_id'],
            'lat_field': 'latitude',
            'long_field': 'longitude'
        })
        metadata = MetaData()
        table = Table(self.resource['resource_id'], metadata, autoload=True, autoload_with=TestMapActions.engine)
        s = select([
            table.c['latitude'],
            table.c['longitude'],
            func.st_x(table.c['_geom']).label('x'),
            func.st_y(table.c['_geom']).label('y'),
            table.c['skip']
        ]).where(table.c['_the_geom_webmercator'].isnot(None))
        r = TestMapActions.engine.execute(s)
        try:
            assert r.rowcount == 2, "Did not report the expected rows. Expecting {}, got {}".format(2, r.rowcount)
            for row in r:
                assert float(row['x']) == float(row['longitude']), "Longitude not correctly set"
                assert float(row['y']) == float(row['latitude']), "Latitude not correctly set"
                assert row['skip'] == 'no', "Row was included which should have not"
        except:
            raise
        finally:
            r.close()