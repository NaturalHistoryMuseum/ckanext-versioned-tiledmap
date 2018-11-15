#!/usr/bin/env python
# encoding: utf-8

import re


# Template helpers
def mustache_wrapper(str):
    return '{{' + str + '}}'


def dwc_field_title(field):
    """
    Convert a DwC field name into a label - split on uppercase
    @param field:
    @return: str label
    """
    title = re.sub('([A-Z]+)', r' \1', field)
    title = title[0].upper() + title[1:]
    return title
