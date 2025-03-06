import os
from typing import Optional
from uuid import uuid4

import requests
from fastapi import APIRouter

from utils.log import timeit

HLS_SERVER = os.getenv('HLS_SERVER', 'localhost')

router = APIRouter(prefix='/rtsp_manager', tags=['rtsp_manager'])


@router.post('/rtsp_to_hls')
def rtsp_to_hls(rtsp_url: str, alias: Optional[str] = None):
    if not alias:
        alias = str(uuid4())[0:4]
    data = {
        "uri": rtsp_url,
        "alias": f"hls_{alias}",
    }
    print("data", data)
    try:
        respons_from_server = requests.post(HLS_SERVER + "/start", json=data)
        print("make request to hls server", respons_from_server.json())

        respons_from_server.raise_for_status()
        return respons_from_server.json()
    except Exception as e:
        return {"error": str(e)}


@router.post('/rtsp_to_hls_stop/{alias}')
def rtsp_to_hls_stop(
        alias: str, id: Optional[str] = None, remove: Optional[bool] = False, wait: Optional[bool] = False
):
    # {
    #     "id": "40b1cc1b-bf19-4b07-8359-e934e7222109",
    #     "alias": "camera1",
    #     "remove": true, // optional - indicates if stream should be removed as well from list or not
    #     "wait": false // optional - indicates if the call should wait for the stream to stop
    # }
    try:
        respons_from_server = requests.post(
            HLS_SERVER + "/stop", json={"alias": alias, "id": id, "remove": remove, "wait": wait}
        )
        respons_from_server.raise_for_status()
        return respons_from_server.json()
    except Exception as e:
        return {"error": str(e)}


@router.get('/rtsp_to_hls_list')
def rtsp_to_hls_list():
    try:
        respons_from_server = requests.get(HLS_SERVER + "/list")
        respons_from_server.raise_for_status()
        return respons_from_server.json()
    except Exception as e:
        return {"error": str(e)}
