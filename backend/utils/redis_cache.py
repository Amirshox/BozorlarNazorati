import json
import os
from datetime import datetime

import redis
from dotenv import find_dotenv, load_dotenv
from redis import Redis

load_dotenv(find_dotenv())

REDIS_URL = os.getenv("REDIS_URL")


def serialize_tenant_entity(entity):
    """Convert a TenantEntity instance to a serializable format, including handling of datetime."""
    if entity:
        result = {}
        for key, value in entity.__dict__.items():
            if key.startswith("_"):
                continue  # Skip SQLAlchemy internal attributes
            elif isinstance(value, datetime):
                result[key] = value.isoformat()  # Convert datetime to ISO 8601 string
            else:
                result[key] = value
        return result
    return None


def get_redis_connection():
    return redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)


def get_from_redis(redis_client: Redis, key: str):
    value = redis_client.get(key)
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


def serialize_datetime(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def set_to_redis(redis_client: Redis, key: str, value, expire: int = 1800):
    redis_client.set(key, json.dumps(value, default=serialize_datetime), ex=expire)
    return value


def set_to_redis_unlimited(redis_client: Redis, key: str, value):
    redis_client.set(key, json.dumps(value))
    return value
