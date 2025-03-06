import os
import pytz
import json
import logging
import secrets
import sentry_sdk
from fastapi import FastAPI
from routers import user_managment
from logging.config import fileConfig
from websocket_manager import manager
from routers import equipment_managment
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from fastapi import WebSocket, WebSocketDisconnect
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html

uzbekistan_timezone = pytz.timezone('Asia/Tashkent')

OPENAPI_DASHBOARD_LOGIN = os.getenv('USERNAME', 'admin')
OPENAPI_DASHBOARD_PASSWORD = os.getenv('PASSWORD', 'ping1234')

security = HTTPBasic()

sentry_sdk.init(
    dsn=os.getenv('SENTRY_DSN'),
    traces_sample_rate=0.5,
    profiles_sample_rate=1.0,
)

# setup loggers
logging.config.fileConfig('logging.conf', disable_existing_loggers=False)

# get root logger
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Camera  Mangment Tool",
    description="This Camera Mangment tool uses websocket connection by the debice",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

logger.info("Starting application...")


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


@app.get("/docs")
async def get_documentation(username: str = Depends(get_current_username)):
    return get_swagger_ui_html(openapi_url="/openapi.json", title="docs")


@app.get("/redoc", include_in_schema=False)
async def get_redoc_documentation(username: str = Depends(get_current_username)):
    return get_redoc_html(openapi_url="/openapi.json", title="docs")


@app.get("/openapi.json")
async def openapi(username: str = Depends(get_current_username)):
    return get_openapi(title="FastAPI", version="0.1.0", routes=app.routes)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:  # Add a loop to keep processing messages
            data = await manager.get_message(websocket)  # This waits for a message from the queue
            dict_data = json.loads(data)
            # logger.info(f"CONNECTION VIA WEBSOCKET {websocket.client.host}")
            is_sent = False
            # Process the message
            if "request_type" in dict_data:
                if dict_data["request_type"] == "deviceOnline":
                    # {'request_type': 'deviceOnline', 'device_name': 'IPCamera', 'device_id': 'H010001172B0100010772',
                    #  'lib_platform_version': 'platform v6.0.3', 'lib_ai_version': 'ai zx v20231011',
                    #  'software_version': '10.001.11.1_MAIN_V4.18(240304)', 'device_mac': 'bc-07-18-01-5d-bd',
                    #  'sign': 'ddee77a61189094d3dee299c3398675d', 'sign_tby': 'fb7f6dbaeb7921b5e9c99288d41e2fed'}
                    logger.info(f"I AM ONLINE ID: {dict_data['device_id']}")
                    manager.acquaintance_connections[dict_data["device_id"]] = websocket
                    if not is_sent:
                        is_sent = True
                        interval_extender = {
                            "resp_type": "deviceOnline",
                            "device_id": dict_data["device_id"],
                            "code": 0,
                            "log": "'deviceOnline'success"
                        }
                        logger.info(f"SENDING DEVICE ONLINE RESPONSE {interval_extender}")
                        json_data = json.dumps(interval_extender)
                        await manager.send_personal_message(json_data, websocket)
                if dict_data["request_type"] == "heartbeat":
                    logger.info(f"LUP ID: {dict_data['device_id']}")
                    # {'request_type': 'heartbeat', 'IP': '192.168.100.112', 'device_id': 'H010001180F0100010016',
                    #  'device_name': 'IPCamera', 'timestamp': 1717157989, 'user_num': 5749,
                    #  'sign_tby': '6b88a26efda12e9a40cfda4e6f7b3654'}
                    heartbeat_response = {
                        "resp_type": "heartbeat",
                        "device_id": dict_data["device_id"],
                        "code": 0,
                        "log": "'heartbeat'success"
                    }
                    logger.info(f"DUP ID: {dict_data['device_id']}")
                    json_data = json.dumps(heartbeat_response)
                    await manager.send_personal_message(json_data, websocket)
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
        logger.info(f"CONNECTION VIA WEBSOCKET {websocket.client.host} DISCONNECTED")

app.include_router(equipment_managment.routerALL)
app.include_router(equipment_managment.router, dependencies=[Depends(get_current_username)])
app.include_router(user_managment.router, dependencies=[Depends(get_current_username)])

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)
