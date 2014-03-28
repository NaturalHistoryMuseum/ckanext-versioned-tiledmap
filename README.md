ckanext-map
===========

A CKAN plugin to replace the default map preview with one that uses a
<a href="https://github.com/CartoDB/Windshaft">Windshaft</a> server to generate the map tiles and interactivity layer.

The point of this extention is to provide maps that can handle millions of data points. The Windshaft server itself is
available at
<a href="https://github.com/NaturalHistoryMuseum/nhm-windshaft-app">https://github.com/NaturalHistoryMuseum/nhm-windshaft-app</a>

setup
=====

Postgis
-------

You postgresql database must have <a href="http://postgis.net/">postgis</a> support. On Ubuntu 12.04 LTS, assuming a
default postgres 9.1 install you can setup your database by doing:

```bash
  sudo apt-get install -y postgresql-9.1-postgis
  sudo -u postgres psql -d ${DATASTORE_DB_NAME} -f /usr/share/postgresql/9.1/contrib/postgis-1.5/postgis.sql
  sudo -u postgres psql -d ${DATASTORE_DB_NAME} -c "ALTER TABLE geometry_columns OWNER TO $DB_USER"
  sudo -u postgres psql -d ${DATASTORE_DB_NAME} -c "ALTER TABLE spatial_ref_sys OWNER TO $DB_USER"
  sudo -u postgres psql -d ${DATASTORE_DB_NAME} -f /usr/share/postgresql/9.1/contrib/postgis-1.5/spatial_ref_sys.sql
```

Where ```DATASTORE_DB_NAME``` is the name of your postgres database that holds the datastore name, and ```DB_USER``` is
your database user.

Windshaft server
----------------

You then need to setup a windshaft server. You can download the server at
<a href="https://github.com/NaturalHistoryMuseum/nhm-windshaft-app">https://github.com/NaturalHistoryMuseum/nhm-windshaft-app</a>
and configure it to set up the ckan datastore database.

Configuration
=============

The plugin supports the following configuration options:

- map.windshaft.host: The hostname of the windshaft server. Defaults to 127.0.0.1 ;
- map.windshaft.port: The port for the windshaft server. Defaults to 4000 ;
- map.winsdhaft_database: The database name to pass to the windshaft server. Defaults
  to the database name from the datastore URL ;
- map.geom_field: Geom field. Defaults to ```the_geom_webmercator```. Do not change this unless you know what you are
  doing. Must be 3857 type field;
- map.geom_field_4326: The 4326 geom field. Defaults to ```geom```. Do not change this unless you know what you are
  doing. Must be 4326 type field ;
- map.interactivity: List of SQL fields to use for the interactivity layer. Defaults to ```_id, count```. Note that
  ```count``` refers to the count, while all other fields *must* exist in the database table. The plugin uses aliases
  starting with ```_mapplugin``` while building the query, so there should be no fields named in this way ;
- map.tile_layer.url: URL of the tile layer. Defaults to http://otile1.mqcdn.com/tiles/1.0.0/map/{z}/{x}/{y}.jpg ;
- map.tile_layer.opacity: Opacity of the tile layer. Defaults to 0.8 ;
- map.initial_zoom.min: Minimum zoom level for initial display of dataset, defaults to 2 ;
- map.initial_zoom.max: Maximum zoom level for initial display of dataset, defaults to 6.

Usage
=====

The plugin also provides some API actions to add the required geometry fields to a given datastore resource. This is
called as:

```python
    import ckan.plugins.toolkit as toolkit
    create_geom_columns = toolkit.get_action('create_geom_columns')
    create_geom_columns(TestMapActions.context, {
        'resource_id': resource_id,
        'lat_field': 'latitude',
        'long_field': 'longitude'
    })
```

The code will add the two geometry columns (by default ```geom``` and ```the_geom_webmercator```) to the given resource
database table, and will populate those fields using the (existing) ```latitude``` and ```longitude``` fields.

You can also create the columns without populating the table by passing in ```'populate': False```. You can then
populate the columns later (or update already populated columns) by doing:

```python
    import ckan.plugins.toolkit as toolkit
    update_geom_columns = toolkit.get_action('updated_geom_columns')
    updated_geom_columns(TestMapActions.context, {
        'resource_id': resource_id,
        'lat_field': 'latitude',
        'long_field': 'longitude'
    })
```


For both actions you can override the default geometry column names by passing ```geom_field``` and
```geom_field_4326``` (only if you know what you are doing!)

And finally, the plugin also provides paster scripts to add geometry columns to a given datastore resource; though we
recommend calling the actions from your own code you can use this initially when testing/setting up:

```
paster ckanextmap add-all-geoms -c <path to your config file>
```