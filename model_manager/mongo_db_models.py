import os
import motor.motor_asyncio
from typing import Optional
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv, find_dotenv
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, HttpUrl, Field
from pydantic import ConfigDict, BaseModel, Field, EmailStr
# from pydantic.functional_validators import BeforeValidator # This is not needed

# load .env file from one directory up
load_dotenv(find_dotenv())

MONGO_DB_URL = os.environ.get("MONGODB_URL")


def get_mongo_db():
    return motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URL)["smart-camera"]


class AgePredictionHourlyV1Request(BaseModel):
    """
    Container for age prediction request
    """

    company_type: str
    hour_of_day: int
    day_of_week: int


class AgePredictionHourlyV1Response(BaseModel):
    hour: int
    visitor_count: int
    average_age: str


class SexPredictionHourlyV1Request(BaseModel):

    company_id: int
    company_type: str
    hour: int


class SexPredictionHourlyV1Response(BaseModel):
    hour: int
    visitor_count: int
    male_percentage: float


class EncoderArguments(BaseModel):
    features: Dict[str, str]


class Encoder(BaseModel):
    encoder_name: str
    encoder_url: HttpUrl
    encoder_bucket: str
    training_date: datetime
    dataset_size: int
    encoder_arguments: EncoderArguments


class ModelArgumentsFeatures(BaseModel):
    company_type: str
    hour_of_day: str
    day_of_week: str


class ModelArgumentsTarget(BaseModel):
    visitor_count: str
    average_age: str


class ModelArguments(BaseModel):
    features: ModelArgumentsFeatures
    target: ModelArgumentsTarget


class Model(BaseModel):
    _id: str = Field(..., alias="_id")
    model_type: str
    model_version: int
    model_name: str
    model_url: HttpUrl
    bucket_name: str
    training_date: datetime
    dataset_size: int
    accuracy: float
    encoder: Encoder
    model_arguments: ModelArguments

    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True


class AgePredictionHourlyV1ResponseModelMeta(BaseModel):
    predictions: List[AgePredictionHourlyV1Response]
    model:Optional[Model]