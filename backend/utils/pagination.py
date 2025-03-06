from fastapi import Query
from fastapi_pagination import Page

CustomPage = Page.with_custom_options(size=Query(20, ge=1, le=100))
