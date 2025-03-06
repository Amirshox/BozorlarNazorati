import json
import logging
from uuid import uuid4
from websocket_manager import manager
from fastapi import APIRouter, HTTPException, status
from schema.identify_managment import GetpicRecognition
from utilities_manager import generate_md5, get_error_description
from schema.user_managment import (
    QueryTheUserListInformation,
    ObtainUserInfo,
    DeleteUserList,
    DeleteUser,
    AddUser,
    UpdateUser,
)

router = APIRouter(
    prefix="/device/{device_id}/user_management", tags=["user management"]
)

logger = logging.getLogger(__name__)


@router.post("/queryTheUserListInformation")
async def query_user_list_information(
    device_id: str, request: QueryTheUserListInformation
):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:4]
    message = {
        "request_type": "getUserList",
        "request_id": request_id,
        "pass": generate_md5(request.password),
        "device_id": device_id,
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=15)
        if response["code"] == 0:
            return response
        else:
            desciption = get_error_description(response["code"])
            payload = {
                "status": "error",
                "response": response,
                "description": desciption,
            }
            raise HTTPException(status_code=400, detail=payload)
    except TimeoutError as e:
        raise HTTPException(status_code=408, detail=str(e))


@router.post("/addUser")
async def add_user(device_id: str, request: AddUser):
    logger.info(f"Adding user {request.user_id} to device {device_id}")
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:4]
    message = {
        "request_type": "addUser",
        "request_id": request_id,
        "pass": generate_md5(request.password),
        "device_id": device_id,
        "user_list": request.user_list,
        "user_id": request.user_id,
        "group": request.group,
        "image_content": request.image_content,
        "image_type": request.image_type,
        "user_info": request.user_info.dict(),
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response_dict = await manager.wait_for_message(
            device_id, request_id, timeout=100
        )
        if response_dict["code"] == 0:
            return response_dict
        else:
            description = get_error_description(response_dict["code"])
            payload = {
                "status": "error",
                "response": response_dict,
                "description": description,
            }
            raise HTTPException(status_code=400, detail=payload)
    except TimeoutError as e:
        raise HTTPException(status_code=408, detail=str(e))


@router.post("/updateUser")
async def update_user(device_id: str, user_id: str, request: UpdateUser):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:4]
    message = {
        "request_type": "updateUser",
        "request_id": request_id,
        "pass": generate_md5(request.password),
        "device_id": device_id,
        "user_id": user_id,
        "group": request.group,
        "image_content": request.image_content,
        "image_type": request.image_type,
        "user_info": request.user_info.dict(),
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=15)
        if response["code"] == 0:
            return response
        else:
            description = get_error_description(response["code"])
            payload = {
                "status": "error",
                "response": response,
                "description": description,
            }
            raise HTTPException(status_code=400, detail=payload)
    except TimeoutError as e:
        raise HTTPException(status_code=408, detail=str(e))


@router.post("/deleteUser")
async def delete_user(device_id: str, request: DeleteUser):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:4]
    message = {
        "request_type": "deleteUser",
        "request_id": request_id,
        "pass": generate_md5(request.password),
        "device_id": device_id,
        "user_id": request.user_id,
        "group": request.group,
        "user_list": request.user_list,
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=15)
        return {"status": "success", "response": response}
    except TimeoutError as e:
        raise HTTPException(status_code=408, detail=str(e))


@router.post("/deleteUserList")
async def delete_user_list(device_id: str, request: DeleteUserList):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:4]
    message = {
        "request_type": "delUserList",
        "request_id": request_id,
        "pass": generate_md5(request.password),
        "user_list": request.user_list,
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=15)
        if response["code"] == 0:
            return response
        else:
            description = get_error_description(response["code"])
            payload = {
                "status": "error",
                "response": response,
                "description": description,
            }
            raise HTTPException(status_code=400, detail=payload)
    except TimeoutError as e:
        raise HTTPException(status_code=408, detail=str(e))


@router.post("/obtainUserInfo")
async def obtain_user_info(device_id: str, requets: ObtainUserInfo):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:4]
    message = {
        "request_type": "getUserInfo",
        "request_id": request_id,
        "pass": generate_md5(requets.password),
        "user_id": requets.user_id,
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=15)
        if response["code"] == 0:
            return response
        else:
            description = get_error_description(response["code"])
            payload = {
                "status": "error",
                "response": response,
                "description": description,
            }
            raise HTTPException(status_code=400, detail=payload)
    except TimeoutError as e:
        raise HTTPException(status_code=408, detail=str(e))


@router.post("/picRecognition")
async def pic_recognition(device_id: str, requets: GetpicRecognition):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:4]
    message = {
        "request_type": "picRecognition",
        "request_id": request_id,
        "pass": generate_md5(requets.password),
        "device_id": device_id,
        "image_type": requets.image_type,
        "image_content": requets.image_content,
        "min_fscore": requets.min_fscore,
        "max_result_num": requets.max_result_num,
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=15)
        if response["code"] == 0:
            return response
        else:
            description = get_error_description(response["code"])
            payload = {
                "status": "error",
                "response": response,
                "description": description,
            }

            raise HTTPException(status_code=400, detail=payload)
    except TimeoutError as e:
        raise HTTPException(status_code=408, detail=str(e))
