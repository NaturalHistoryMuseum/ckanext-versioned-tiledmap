#!/usr/bin/env python
# encoding: utf-8
#
# This file is part of a project
# Created by the Natural History Museum in London, UK

import re

from ckan.plugins import toolkit
from ckanext.tiledmap.lib.utils import get_resource_datastore_fields


def colour_validator(value, context):
    """
    Validate a value is a CSS hex color.

    :param value: the value to validate
    :param context: the context within which this validation is taking place
    :return: the validated value
    """
    if re.match('^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$', value):
        if value[0] != '#':
            return f'#{value}'
        else:
            return value
    else:
        raise toolkit.Invalid(
            toolkit._(
                'Colors must be formed of three or six RGB hex value, '
                'optionally preceded by a # sign (eg. #E55 or #F4A088)'
            )
        )


def float_01_validator(value, context):
    """
    Validates that the value is a float number between 0 and 1.

    :param value: the value
    :param context: the context within which this validation is taking place
    :return: the validated value
    """
    try:
        value = float(value)
    except ValueError:
        raise toolkit.Invalid(toolkit._('Must be a decimal number, between 0 and 1'))
    if value < 0 or value > 1:
        raise toolkit.Invalid(toolkit._('Must be a decimal number, between 0 and 1'))
    return value


def is_datastore_field(value, context):
    """
    Check that the fields are indeed a datastore fields.

    :param value: the value to validate
    :param context: the context within which this validation is taking place
    :return: the value
    """
    passed_fields = value if isinstance(value, list) else [value]
    fields = get_resource_datastore_fields(toolkit.g.resource['id'])
    invalid_fields = [field for field in passed_fields if field not in fields]
    if invalid_fields:
        raise toolkit.Invalid(f'Invalid parameters: {",".join(invalid_fields)}')
    return value


def is_view_id(value, context):
    """
    Ensure this is a view id on the current resource.

    :param value: the value to validate
    :param context: the context within which this validation is taking place
    :return: the value
    """
    if value:
        data = {'id': toolkit.g.resource['id']}
        views = toolkit.get_action('resource_view_list')(context, data)
        if value not in [view['id'] for view in views]:
            raise toolkit.Invalid(toolkit._('Must be a view on the current resource'))
    return value
