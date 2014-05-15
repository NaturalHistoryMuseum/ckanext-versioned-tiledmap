from setuptools import setup, find_packages
import sys, os

version = '0.1'

setup(
	name='ckanext-tiledmap',
	version=version,
	description="",
	long_description="""\
	""",
	classifiers=[], # Get strings from http://pypi.python.org/pypi?%3Aaction=list_classifiers
	keywords='',
	license='',
	packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
	namespace_packages=['ckanext', 'ckanext.tiledmap'],
	include_package_data=True,
	zip_safe=False,
	install_requires=[
		# -*- Extra requirements: -*-
	],
	entry_points=\
	"""
        [ckan.plugins]
            tiledmap = ckanext.tiledmap.plugin:TiledMapPlugin
        [paste.paster_command]
            ckanexttiledmapmap=ckanext.tiledmapmap.commands.add_geom:AddGeomCommand
	""",
)
