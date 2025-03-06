from fastapi import Request
from nats_client import NATSClient

async def get_nats_client(request: Request) -> NATSClient:
    return request.app.state.nats_client