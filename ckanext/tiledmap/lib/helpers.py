import re
from sqlalchemy import func
from sqlalchemy.types import UserDefinedType

class Geometry(UserDefinedType):
    def get_col_spec(self):
        return "GEOMETRY"

    def bind_expression(self, bindvalue):
        return func.ST_GeomFromText(bindvalue, type_=self)

    def column_expression(self, col):
        return col


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
