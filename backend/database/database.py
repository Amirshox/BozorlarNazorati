import os
from typing import Iterator

import motor.motor_asyncio
import pika
from aio_pika import connect_robust
from dotenv import find_dotenv, load_dotenv
from sqlalchemy import QueuePool, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

load_dotenv(find_dotenv(), override=True)
MONGO_DB_URL = os.environ.get("MONGODB_URL")
REDIS_URL = os.environ.get("REDIS_URL")

RABBIT_MQ_HOST = os.getenv("RABBIT_MQ_HOST")
RABBIT_MQ_PORT = int(os.getenv("RABBIT_MQ_PORT", 5678))
RABBIT_MQ_USERNAME = os.getenv("RABBIT_MQ_USER", "guest")
RABBIT_MQ_PASSWORD = os.getenv("RABBIT_MQ_PASSWORD", "guest")

DATABASE_URL = os.getenv("POSTGRESQL_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

Base = declarative_base()

engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=5,
    pool_timeout=60,
    pool_recycle=1800,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_pg_db() -> Iterator[Session]:
    """FastAPI dependency that provides a sqlalchemy session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_mongo_db():
    return motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URL)["smart-camera"]


def get_logs_db():
    return motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URL)["status-and-logs"]


def get_identity_celery_mongo_db():
    return motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URL)["identity_callback"]


def get_cron_celery_mongo_db():
    return motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URL)["cron"]


def get_analytics_cache_db():
    return motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URL)["analytics_cache"]


def get_pinfl_data_mongo_db():
    return motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URL)["pinfl-data"]


def get_one_system_mongo_db():
    return motor.motor_asyncio.AsyncIOMotorClient(MONGO_DB_URL)["one-system"]


async def get_rabbitmq_connection():
    connection = await connect_robust(
        f"amqp://{RABBIT_MQ_USERNAME}:{RABBIT_MQ_PASSWORD}@{RABBIT_MQ_HOST}:{RABBIT_MQ_PORT}/"
    )
    try:
        yield connection
    finally:
        await connection.close()


def get_rabbitmq_sync_connection():
    # Authentication credentials
    credentials = pika.PlainCredentials(RABBIT_MQ_USERNAME, RABBIT_MQ_PASSWORD)

    connection_params = pika.ConnectionParameters(
        host=RABBIT_MQ_HOST,
        port=RABBIT_MQ_PORT,
        credentials=credentials,
    )

    return pika.BlockingConnection(connection_params)


async def init_db():
    db = get_mongo_db()
    # Create the timeseries collection
    await db.create_collection(
        "devices_events",
        timeseries={
            "timeField": "timestamp",  # Specify the field that holds the timestamp
            "metaField": "device_id",  # Optional. Use if you want to query by this field efficiently.
            "granularity": "seconds",  # Granularity of the buckets. Choose based on your data rate.
        },
    )

    # It's also a good practice to create indexes on any fields you'll query often
    await db["devices"].create_index([("timestamp", 1)])

    jetson_device_db = get_logs_db()

    await jetson_device_db.create_collection("status_revisions")

    await jetson_device_db["status_revisions"].create_index("created_at", expireAfterSeconds=300)
