#!/usr/bin/env python
# encoding: utf-8
#
# This file is part of a project
# Created by the Natural History Museum in London, UK

from setuptools import find_packages, setup

version = u'0.1'

setup(
    name=u'ckanext-versioned-tiledmap',
    version=version,
    description=u'',
    long_description=u'',
    classifiers=[],
    keywords=u'',
    license=u'',
    packages=find_packages(exclude=[u'ez_setup', u'examples', u'tests']),
    namespace_packages=[u'ckanext', u'ckanext.tiledmap'],
    include_package_data=True,
    zip_safe=False,
    install_requires=[],
    entry_points=
    u'''
    [ckan.plugins]
    versioned_tiledmap = ckanext.tiledmap.plugin:VersionedTiledMapPlugin
    ''',
    )
