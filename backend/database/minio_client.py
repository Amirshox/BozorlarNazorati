import os
from functools import lru_cache

from dotenv import find_dotenv, load_dotenv
from minio import Minio

load_dotenv(find_dotenv())

minioClient = Minio(
    os.getenv("MINIO_ENDPOINT"),
    os.getenv("MINIO_ACCESS_KEY"),
    os.getenv("MINIO_SECRET_KEY"),
    region=os.getenv("AWS_STORAGE_REGION") if os.getenv("AWS_STORAGE_REGION") else "us-east-1",
    secure=False,
)

minioSSDClient = Minio(
    os.getenv("MINIO_SSD_ENDPOINT"),
    os.getenv("MINIO_SSD_ACCESS_KEY"),
    os.getenv("MINIO_SSD_SECRET_KEY"),
    region=os.getenv("AWS_STORAGE_REGION") if os.getenv("AWS_STORAGE_REGION") else "us-east-1",
    secure=False,
)


@lru_cache
def get_minio_client():
    return minioClient


@lru_cache
def get_minio_ssd_client():
    return minioSSDClient
