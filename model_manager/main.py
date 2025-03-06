import io
import os
import pytz
import logging
import secrets
import sentry_sdk
from joblib import load
from typing import List
from fastapi import FastAPI
from minio import Minio, S3Error
from logging.config import fileConfig
from mongo_db_models import get_mongo_db
from contextlib import asynccontextmanager
from fastapi.staticfiles import StaticFiles
from fastapi_utils.tasks import repeat_every
from fastapi.openapi.utils import get_openapi
from fastapi import HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from manager_utilies import preprocess_age, get_latest_age_model, get_latest_sex_model, preprocess_sex
from mongo_db_models import (
    AgePredictionHourlyV1Request, AgePredictionHourlyV1Response, SexPredictionHourlyV1Request,
    SexPredictionHourlyV1Response, AgePredictionHourlyV1ResponseModelMeta
)


uzbekistan_timezone = pytz.timezone('Asia/Tashkent')

OPENAPI_DASHBOARD_LOGIN = os.getenv('USERNAME', 'admin')
OPENAPI_DASHBOARD_PASSWORD = os.getenv('PASSWORD', 'ping1234')

MINIO_ENDPOINT = os.getenv('MINIO_ENDPOINT', 'localhost:9000')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY', 'minio')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY', 'minio123')

minio_client = Minio(
    MINIO_ENDPOINT,
    MINIO_ACCESS_KEY,
    MINIO_SECRET_KEY,
    region=os.getenv("AWS_STORAGE_REGION") if os.getenv("AWS_STORAGE_REGION") else "us-east-1",
    secure=False,
)

age_model, le, model_meta = None, None, None


sex_model, sex_le = None, None

security = HTTPBasic()

sentry_sdk.init(
    dsn=os.getenv('SENTRY_DSN'),
    traces_sample_rate=0.5,
    profiles_sample_rate=1.0,
)

mongo_db = get_mongo_db()
model_collection = mongo_db["models"]

# setup loggers
logging.config.fileConfig('logging.conf', disable_existing_loggers=False)

# get root logger
logger = logging.getLogger(__name__)
@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup_event()
    yield


app = FastAPI(
    title="AI Prediction API",
    description="sdk for AI prediction",
    version="1.0.0",
    docs_url = None,
    redoc_url = None,
    openapi_url = None,
    lifespan=lifespan
)

logger.info("Starting application...")

security = HTTPBasic()


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
    return get_swagger_ui_html(openapi_url="/openapi.json", title="docs", oauth2_redirect_url="/docs/oauth2-redirect",
                               swagger_js_url="/static/swagger-ui-bundle.js", swagger_css_url="/static/swagger-ui.css")


@app.get("/redoc", include_in_schema=False)
async def get_redoc_documentation(username: str = Depends(get_current_username)):
    return get_redoc_html(openapi_url="/openapi.json", title="docs")


@app.get("/openapi.json")
async def openapi(username: str = Depends(get_current_username)):
    return get_openapi(title = "FastAPI", version="0.1.0", routes=app.routes)

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.post("/age-prediction-hourly-v1", response_model=AgePredictionHourlyV1ResponseModelMeta)
async def age_prediction_hourly_v1(request: List[AgePredictionHourlyV1Request]):

    if age_model is None or le is None:
        raise HTTPException(status_code=500, detail="Model not loaded")
    data = preprocess_age(request, le)
    predictions = age_model.predict(data)


    result = []
    for i in range(len(request)):
        result.append(AgePredictionHourlyV1Response(
            hour=request[i].hour_of_day,
            visitor_count=predictions[i][0],
            average_age=predictions[i][1]
        ))
    return {
        "predictions": result,
        "model": model_meta
    }

# @app.post("/sex-prediction-hourly-v1", response_model=List[SexPredictionHourlyV1Response])
# async def sex_prediction_hourly_v1(request: List[SexPredictionHourlyV1Request]):
#
#     if sex_model is None or sex_le is None:
#         raise HTTPException(status_code=500, detail="Model not loaded")
#     # Preprocess input data
#     processed_data = preprocess_sex(request, sex_le)  # encoder should be the loaded/fitted OneHotEncoder instance
#
#
#     print(processed_data)
#     # Predict with the model
#     # Ensure your model is loaded and named appropriately (e.g., sex_model)
#     predictions = sex_model.predict(processed_data)
#
#     # Construct and return the response
#     # Adjust the response construction as per your actual requirements
#     response = []
#     for req, pred in zip(request, predictions):
#         response.append(SexPredictionHourlyV1Response(
#             hour=req.hour,
#             visitor_count=int(pred[0]),
#             male_percentage=pred[1] * 100  # Assuming pred[1] is the proportion of males, converted to percentage
#         ))
#     return response

#startup event
#repeat every 24 hours


@app.on_event("startup")
@repeat_every(seconds=60*60*24)
async def startup_event():
    global age_model, le, model_meta
    try:
        age_model, le, model_meta = await get_latest_age_model()
    except Exception as e:
        logger.error(f"Error occurred while loading model: {e}")

    # global sex_model, sex_le
    # try:
    #     sex_model, sex_le = await get_latest_sex_model()
    # except Exception as e:
    #     logger.error(f"Error occurred while loading model: {e}")
origins = [
    "*"
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*']
)


