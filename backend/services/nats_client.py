# from typing import Optional
#
# from nats.aio.client import Client as NATS
#
# from config import NATS_SERVER_URL
#
# # A global reference to the NATS client; starts as None
# nats_client: Optional[NATS] = None
#
#
# async def init_nats_connection(server_url: str = NATS_SERVER_URL) -> NATS:
#     """
#     Initializes the global NATS client if not already connected.
#     """
#     global nats_client
#     if nats_client is None or not nats_client.is_connected:
#         client = NATS()
#         await client.connect(servers=[server_url])
#         nats_client = client
#         print(f"[NATS] Connected to NATS at {server_url}")
#     return nats_client
#
#
# async def close_nats_connection():
#     """
#     Closes the global NATS client if it’s currently connected.
#     """
#     global nats_client
#     if nats_client and nats_client.is_connected:
#         await nats_client.close()
#         print("[NATS] Disconnected from NATS.")
#     nats_client = None
#
#
# def get_nats_client() -> NATS:
#     """
#     Retrieves the global NATS client. Raises an error if it's not connected.
#     """
#     global nats_client
#     if nats_client is None or not nats_client.is_connected:
#         raise RuntimeError("NATS client is not initialized or is disconnected.")
#     return nats_client
