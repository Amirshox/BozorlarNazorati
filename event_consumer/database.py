from typing import Iterator
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import os
from dotenv import load_dotenv, find_dotenv


# load .env file from one directory up
load_dotenv(find_dotenv())

DATABASE_URL = os.getenv("POSTGRESS_URL")  # or other relevant config var
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

Base = declarative_base()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=create_engine(DATABASE_URL, pool_size=10, max_overflow=20))
def get_db() -> Iterator[Session]:
    """FastAPI dependency that provides a sqlalchemy session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from pymongo import MongoClient
from pymongo import errors

MONGODB_URL = os.getenv("MONGODB_URL")
MONG0DB_DATABASE = os.getenv("MONG0DB_DATABASE", "smart-camera")
ROI_COLLECTION = os.getenv("ROI_COLLECTION", "roi")
LINE_COLLECTION = os.getenv("LINE_COLLECTION", "line-crossing")

def get_mongo_client():
    return MongoClient(MONGODB_URL)[MONG0DB_DATABASE]

def get_roi_collection():
    return get_mongo_client()[ROI_COLLECTION]

def get_line_collection():
    return get_mongo_client()[LINE_COLLECTION]

db = get_mongo_client()
if ROI_COLLECTION not in db.list_collection_names():
    db.create_collection(
        ROI_COLLECTION,
        timeseries={
            'timeField': '@timestamp',
            'metaField': 'object',  # Optional: specify a field to be used for metadata
            'granularity': 'seconds'  # Optional: specify the granularity of the time series
        }
    )

if LINE_COLLECTION not in db.list_collection_names():
    db.create_collection(
        LINE_COLLECTION,
        timeseries={
            'timeField': '@timestamp',
            'metaField': 'object',  # Optional: specify a field to be used for metadata
            'granularity': 'seconds'  # Optional: specify the granularity of the time series
        }
    )
