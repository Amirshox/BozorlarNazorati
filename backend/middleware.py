import contextlib
import json
import time

from datetime import datetime
from json import JSONDecodeError

from pymongo import MongoClient
from pymongo.errors import DocumentTooLarge
from starlette.concurrency import iterate_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class CustomBaseHTTPMiddleware(BaseHTTPMiddleware):
    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        except RuntimeError as exc:
            if str(exc) == "No response returned.":
                request = Request(scope, receive=receive)
                if await request.is_disconnected():
                    return
            raise

    async def dispatch(self, request, call_next):
        raise NotImplementedError()


class LogMiddleware(CustomBaseHTTPMiddleware):
    def __init__(self, app, mongo_db_url: str, mongo_db_name: str, mongo_db_collection: str):
        super().__init__(app=app)
        self.client = MongoClient(mongo_db_url, maxPoolSize=50)  # Reuse connections with max pool size
        self.db = self.client[mongo_db_name]
        self.collection = self.db[mongo_db_collection]

    async def dispatch(self, request, call_next):
        request_body = await request.body()
        request_time = datetime.now()
        response = await call_next(request)

        taken_time = (datetime.now() - request_time).total_seconds()
        response.headers["X-Process-Time"] = f"{taken_time:0.4f} sec"
        response.headers["X-Server-Time"] = str(int(time.time()))

        if not 200 <= response.status_code < 300:
            response_body_data = [chunk async for chunk in response.body_iterator]
            response.body_iterator = iterate_in_threadpool(iter(response_body_data))

            try:
                response_body_text = response_body_data[0].decode()
            except (IndexError, UnicodeDecodeError):
                response_body_text = None

            try:
                request_body = json.loads(request_body)
            except (JSONDecodeError, UnicodeDecodeError):
                request_body = str(request_body)

            log_entry = {
                "response_status_code": response.status_code,
                "request_path": request.url.path,
                "request_method": request.method,
                "request_time": request_time,
                "response_time": datetime.now(),
                "taken_time": taken_time,
                "request_body": request_body,
                "response_body": response_body_text,
                "request_query_params": dict(request.query_params),
                "request_headers": dict(request.headers),
                "response_headers": {"X-Process-Time": f"{taken_time:0.4f} sec"},
                "username": str(request.user),
            }
            with contextlib.suppress(DocumentTooLarge):
                self.collection.insert_one(log_entry)

        return response
