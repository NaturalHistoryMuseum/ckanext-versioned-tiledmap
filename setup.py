from setuptools import setup, find_packages

version = '0.1'

setup(
	name='ckanext-versioned-tiledmap',
	version=version,
	description="",
	long_description="",
	classifiers=[],
	keywords='',
	license='',
	packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
	namespace_packages=['ckanext', 'ckanext.tiledmap'],
	include_package_data=True,
	zip_safe=False,
	install_requires=[],
	entry_points=\
	"""
	[ckan.plugins]
	versioned_tiledmap = ckanext.tiledmap.plugin:VersionedTiledMapPlugin
	""",
)
