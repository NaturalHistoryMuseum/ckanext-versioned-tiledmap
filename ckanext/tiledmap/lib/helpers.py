#!/usr/bin/env python
# encoding: utf-8
#
# This file is part of a project
# Created by the Natural History Museum in London, UK

import re


def mustache_wrapper(s):
    return '{{' + s + '}}'


def dwc_field_title(field):
    '''
    Convert a DwC field name into a label - split on uppercase
    @param field:
    @return: str label
    '''
    title = re.sub('([A-Z]+)', r' \1', field)
    title = f'{title[0].upper()}{title[1:]}'
    return title
