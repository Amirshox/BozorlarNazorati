import os
import secrets

import sentry_sdk
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi_pagination import add_pagination
from starlette.middleware.authentication import AuthenticationMiddleware

from auth.authentication import router as sys_admin_auth_router
from auth.base import JWTAuthBackend
from config import MONGO_DB_URL
from database.database import init_db
from middleware import LogMiddleware
from routers import (
    activity_logs,
    attendance,
    dashboard,
    deepstream_analytics,
    errors_integration,
    file_manger,
    identity,
    identity_customer,
    infrastructure,
    infrastructure_user,
    integration_3rd,
    integrations,
    jetson_device_manager,
    jetson_device_vpn,
    kindergarten,
    module,
    nvdsanalytics,
    region,
    role,
    role_module,
    rtsp_manager,
    smart_camera_event,
    tenant,
    tenant_admin,
    tenant_admin_activation_code,
    tenant_entity,
    tenant_entity_user,
    tenant_profile,
    third_party,
    user,
    user_activation_code,
    user_schedule,
    wanted,
)
from routers.relative import relative_routers

OPENAPI_DASHBOARD_LOGIN = os.getenv("USERNAME", "admin")
OPENAPI_DASHBOARD_PASSWORD = os.getenv("PASSWORD", "ping1234")
SENTRY_DSN = os.getenv("SENTRY_DSN")

security = HTTPBasic()


def profiles_sampler(sampling_context):
    return 0.1


sentry_sdk.init(
    dsn=SENTRY_DSN,
    traces_sample_rate=1.0,
    profiles_sample_rate=1.0,
    profiles_sampler=profiles_sampler,
)


def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, OPENAPI_DASHBOARD_LOGIN)
    correct_password = secrets.compare_digest(credentials.password, OPENAPI_DASHBOARD_PASSWORD)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def create_sub_app(title, version, routers, mount_path=None):
    app_sub = FastAPI(
        title=title,
        version=version,
        docs_url=None,
        redoc_url=None,
        openapi_url="/openapi.json",
    )

    # Include routers in the sub-app
    for router in routers:
        app_sub.include_router(router)

    add_pagination(app_sub)

    def custom_sub_openapi():
        if app_sub.openapi_schema:
            return app_sub.openapi_schema
        openapi_schema = get_openapi(
            title=title,
            version=version,
            routes=app_sub.routes,
        )
        # Set the 'servers' field to include the mount path
        openapi_schema["servers"] = [{"url": mount_path or "/"}]
        app_sub.openapi_schema = openapi_schema
        return app_sub.openapi_schema

    app_sub.openapi = custom_sub_openapi

    @app_sub.get("/docs")
    async def get_sub_app_documentation(username: str = Depends(get_current_username)):
        return get_swagger_ui_html(
            openapi_url=f"{mount_path}/openapi.json",
            title=f"{title} - Docs",
            oauth2_redirect_url="/docs/oauth2-redirect",
            swagger_js_url="/static/swagger-ui-bundle.js",
            swagger_css_url="/static/swagger-ui.css",
        )

    @app_sub.get("/openapi.json")
    async def openapi_sub_app(username: str = Depends(get_current_username)):
        return app_sub.openapi()

    if mount_path:
        app.mount(mount_path, app_sub)

    return app_sub


app = FastAPI(
    title="FastAPI Multi-Tenant",
    description="This is a multi-tenant FastAPI application",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)
app.add_middleware(AuthenticationMiddleware, backend=JWTAuthBackend())
app.add_middleware(
    LogMiddleware,
    mongo_db_url=MONGO_DB_URL,
    mongo_db_name="one-system",
    mongo_db_collection="http_logs",
)


@app.on_event("startup")
async def startup():
    try:
        await init_db()
    except Exception as e:
        print(e)


@app.on_event("shutdown")
async def on_shutdown():
    pass


@app.get("/docs")
async def get_documentation(username: str = Depends(get_current_username)):
    return get_swagger_ui_html(
        openapi_url="openapi.json",
        title="docs",
        oauth2_redirect_url="/docs/oauth2-redirect",
        swagger_js_url="/static/swagger-ui-bundle.js",
        swagger_css_url="/static/swagger-ui.css",
    )


@app.get("/openapi.json")
async def openapi(username: str = Depends(get_current_username)):
    return get_openapi(title="FastAPI", version="0.1.0", routes=app.routes)


@app.get("/.well-known/apple-app-site-association")
def apple_app_site_association():
    return {"webcredentials": {"apps": ["2M9QYY9NBD.uz.realsoftai.kindergarten"]}}


# Include routers in the main app
app.include_router(smart_camera_event.router)
app.include_router(sys_admin_auth_router)

# Define routers for each sub-application
routers_sysadmin = [
    sys_admin_auth_router,
    tenant_profile.router,
    module.router,
    role.router,
    role_module.router,
    tenant.router,
    tenant_admin.router,
    file_manger.router,
    rtsp_manager.router,
    tenant_admin_activation_code.router,
    region.router,
    third_party.router,
]

routers_tenant = [
    sys_admin_auth_router,
    tenant_entity.router,
    user.router,
    user_activation_code.router,
    identity.router,
    integrations.router,
    infrastructure.router,
    nvdsanalytics.router,
    user_schedule.router,
    errors_integration.router,
    wanted.router,
    attendance.tenant_router,
    jetson_device_vpn.router,
    jetson_device_manager.router,
    activity_logs.router,
]

routers_third_party = [
    sys_admin_auth_router,
    integration_3rd.router,
]

routers_customer = [
    sys_admin_auth_router,
    tenant_entity_user.router,
    infrastructure_user.router,
    attendance.router,
    attendance.customer_router,
    dashboard.router,
    identity_customer.mobile_router,
    identity_customer.router,
    deepstream_analytics.router,
    kindergarten.router,
]

# Create sub-applications
app_sysadmin = create_sub_app(  # noqa
    title="Sysadmin API",
    version="1",
    routers=routers_sysadmin,
    mount_path="/sysadmin",
)

app_tenant = create_sub_app(  # noqa
    title="Tenant API",
    version="1",
    routers=routers_tenant,
    mount_path="/tenant",
)

app_third_party = create_sub_app(  # noqa
    title="3rd-Party API",
    version="1",
    routers=routers_third_party,
    mount_path="/3rdparty",
)

app_customer = create_sub_app(  # noqa
    title="Customer API",
    version="1",
    routers=routers_customer,
    mount_path="/customer",
)

app_relative = create_sub_app(  # noqa
    title="Relative API",
    version="1",
    routers=relative_routers,
    mount_path="/relative",
)

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
