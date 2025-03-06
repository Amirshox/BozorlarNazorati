import json
from uuid import uuid4
from websocket_manager import manager
from fastapi import APIRouter, HTTPException, status
from utilities_manager import generate_md5, get_error_description
from schema.equipment_managment import (
    SetPtzControl,
    SetPtzControlResponse,
    SetFaceConfig,
    SetWiredNetworkScheme,
    SetVPNConfScheme,
)
from schema.equipment_managment import (
    FormatTheDisk,
    SetRebootConfigSchema,
    SetResumeTransferSchema,
    SetRtmpConf,
)
from schema.equipment_managment import (
    PassworSettingsSchema,
    EquipmentRebootSchema,
    UpgradeFirmwareSchema,
    SetPlatformServerSchema,
    SetNtpServerSchema,
    GetFmtSnap,
    GetLogFile,
    GetFaceConfig,
)

routerALL = APIRouter(prefix="/devices", tags=["equipment management"])


@routerALL.get("/getAllActiveDevices")
async def get_all_active_devices():
    return {"devices": list(manager.acquaintance_connections.keys())}


router = APIRouter(
    prefix="/device/{device_id}/equipment", tags=["equipment management"]
)


@router.post("/setPassword")
async def set_password(device_id: str, requets: PassworSettingsSchema):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())
    message = {
        "request_type": "setPassword",
        "request_id": request_id,
        "old_password": generate_md5(requets.old_password),
        "new_password": requets.new_password,
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=20)
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


@router.post("/restart")
async def reboot(device_id: str, request: EquipmentRebootSchema):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:4]
    message = {
        "request_type": "restart",
        "request_id": request_id,
        "pass": generate_md5(request.password),
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=20)
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


@router.post("/diskFormat")
async def disk_format(device_id: str, request: FormatTheDisk):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:4]
    message = {
        "request_type": "diskFormat",
        "request_id": request_id,
        "pass": generate_md5(request.password),
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=60)
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


@router.get("/getSoftwareVersion")
async def get_software_version(device_id: str, password: str):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:4]
    message = {
        "request_type": "getSoftVersion",
        "request_id": request_id,
        "pass": generate_md5(password),
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=20)
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


@router.get("/getRebootConf")
async def get_reboot_conf(device_id: str, password: str):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:8]
    message = {
        "request_type": "getRebootConf",
        "request_id": request_id,
        "pass": generate_md5(password),
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=20)
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


@router.post("/setRebootConf")
async def set_reboot_conf(device_id: str, request: SetRebootConfigSchema):
    """
    mode: 0 - disable, 1 - daily, 2 - weekly
    day_week: 0 - Sunday, 1 - Monday, 2 - Tuesday, 3 - Wednesday, 4 - Thursday, 5 - Friday, 6 - Saturday
    """
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:4]
    if request.mode != 0:
        message = {
            "request_type": "setRebootConf",
            "request_id": request_id,
            "pass": generate_md5(request.password),
            "mode": request.mode,
            "day_week": request.day_week,
            "hour": request.hour,
            "minute": request.minute,
        }
    else:
        message = {
            "request_type": "setRebootConf",
            "request_id": request_id,
            "pass": generate_md5(request.password),
            "mode": request.mode,
        }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=20)
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


@router.post("/setResumeTransfer")
async def set_resume_transfer(device_id: str, request: SetResumeTransferSchema):
    """
    Set the network transmission switch. If the network needs to be disconnected, the server must reply to frpic _name
    to the device after receiving the faceRecognition message, and the device will connect to the server and upload all
    the unuploaded to the captured pictures.
    enable: 0 - disable, 1 - enable
    """
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:4]
    message = {
        "request_type": "setResumeTransfer",
        "request_id": request_id,
        "pass": generate_md5(request.password),
        "enable": 1 if request.enable else 0,
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=20)
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


@router.post("/setNtpServer")
async def set_ntp_server(device_id: str, request: SetNtpServerSchema):
    """
    Set the network time synchronization server.
    ntp_server: ntp server address
    update_interval: update interval, unit: minutes
    zone: time zone, default: 20 (Uzbekistan)
    """
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:4]
    message = {
        "request_type": "setNtpServer",
        "request_id": request_id,
        "pass": generate_md5(request.password),
        "ntp_server": request.ntp_server,
        "update_interval": request.update_interval,
        "zone": request.zone,
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=20)
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


@router.post("/upgradeFirmware")
async def upgrade_firmware(device_id: str, request: UpgradeFirmwareSchema):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:8]  # Generating a unique request ID for tracking
    message = {
        "request_type": "upgrade",
        "request_id": request_id,
        "pass": generate_md5(request.password),  # Hashing the password with MD5
        "URL": request.URL,  # Firmware file URL
    }
    # Sending the upgrade request to the device via WebSocket
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        # Waiting for a response from the device
        response = await manager.wait_for_message(
            device_id, request_id, timeout=60
        )  # Extended timeout for firmware
        if response["code"] == 0:
            return {
                "status": "success",
                "log": response.get("log"),
                "device_id": response.get("device_id"),
            }
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


@router.get("/getWiredNetwork")
async def get_wired_network(device_id: str, password: str):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:8]
    message = {
        "request_type": "getWiredNetwork",
        "request_id": request_id,
        "pass": generate_md5(password),
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=20)
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


@router.post("/setWiredNetwork")
async def set_wired_network(device_id: str, request: SetWiredNetworkScheme):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:8]
    message = {
        "request_type": "setWiredNetwork",
        "request_id": request_id,
        "pass": generate_md5(request.password),
        "DHCP": request.DHCP,
        "IP": request.IP,
        "subnet_mask": request.subnet_mask,
        "gateway": request.gateway,
        "manual_dns": request.manual_dns,
        "DNS": request.DNS,
        "DNS2": request.DNS2,
        "device_mac": request.device_mac,
        "webPort": request.webPort,
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=20)
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


@router.get("/getPlatformServer")
async def get_platform_server(device_id: str, password: str):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:8]
    message = {
        "request_type": "getPlatformServer",
        "request_id": request_id,
        "pass": generate_md5(password),
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=20)
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


@router.post("/setPlatformServer")
async def set_platform_server(device_id: str, request: SetPlatformServerSchema):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:8]
    message = {
        "request_type": "setPlatformServer",
        "request_id": request_id,
        "pass": generate_md5(request.password),
        "serverAddr": request.serverAddr,
        "wsServerAddr": request.wsServerAddr,
        "platformSubCode": request.platformSubCode,
        "resumeTransf": request.resumeTransf,
        "wsServerPort": request.wsServerPort,
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=20)
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


@router.get("/getVPNConf")
async def get_vpn_conf(device_id: str, password: str):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:8]
    message = {
        "request_type": "getVPNConf",
        "request_id": request_id,
        "pass": generate_md5(password),
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=20)
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


@router.post("/setVPNConf")
async def set_vpn_conf(device_id: str, request: SetVPNConfScheme):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:8]
    message = {
        "request_type": "setVPNConf",
        "request_id": request_id,
        "pass": generate_md5(request.password),
        "enable": request.enable,
        "ipAddr": request.ipAddr,
        "userName": request.userName,
        "password": request.vpn_password,
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=20)
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


@router.post("/setRtmpConf")
async def set_rtmp_conf(device_id: str, request: SetRtmpConf):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:8]
    message = {
        "request_type": "setRtmpConf",
        "request_id": request_id,
        "channel": request.channel,
        "pass": generate_md5(request.password),
        "RtmpEnable": request.RtmpEnable,
        "RtmpServerAddr": request.RtmpServerAddr,
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=20)
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


# Instructions
# Used by the server to remotely control the device PTZ,
#   the device will continue to execute the command until it receives the stop command.
# name
# Command
# Request Type
# setPtzControl
# name
# definition
# must
# remark
# pass
# Device password
# Y
# string: Device password. The value must be MD5 encrypted and 32-bit.
# request_ id
# Command id
# Y
# number, the unique id of each message
# channel
# channel
# Y
# Number, fixed to 0
# speed_h
# Horizontal moving speed
# Y
# Number, max:100, min:1
# speed_v
# Vertical move speed/preset bit
# Y
# Number, max:100, min:1
# ptz_ cmd
# Head command
# Y
# Number,
# 21: Stop control
# 71: Move to the top left corner, 1: Move up,
# 73: Move to the top right corner, 3: Move left,
# 69: Reset location,
# 4: Move to the right,
# 72: Move to the lower left
# corner,
# 2: Move down,
# 74: Move to the lower right
# corner,
# 10: Multiplier -, 9: multiplier +,
# 6: Focus -, 5: Focus +,
# 8: aperture -, 9: aperture +,
# 13: Light,
# 11: Auxiliary focus,
# 20: Call the current preset bit (speed_v),
# 19: Set the current preset bit (speed_v)

ptz_control_description = """
       Endpoint to control the PTZ (Pan-Tilt-Zoom) of a device. This endpoint accepts commands
       to manipulate the device's position and lens settings. The device will continue to
       execute the command until it receives a stop command.

       - **device_password**: MD5 encrypted device password, 32-bit.
       - **request_id**: Unique command ID for the message.
       - **channel**: Channel number, fixed to 0.
       - **speed_h**: Horizontal moving speed (1 to 100).
       - **speed_v**: Vertical moving speed or preset bit (1 to 100).
       - **ptz_cmd**: PTZ command code. Commands include moving in directions, focusing, 
                      and adjusting aperture, among others.

       Commands for `ptz_cmd` include:
       - `21`: Stop control.
       - `71`: Move to the top left corner.
       - `1`: Move up.
       - `73`: Move to the top right corner.
       - `3`: Move left.
       - `69`: Reset location.
       - `4`: Move right.
       - `72`: Move to the lower left corner.
       - `2`: Move down.
       - `74`: Move to the lower right corner.
       - `10`: Zoom out.
       - `9`: Zoom in.
       - `6`: Focus out.
       - `5`: Focus in.
       - `8`: Decrease aperture.
       - `13`: Light control.
       - `11`: Auxiliary focus.
       - `20`: Call the current preset bit (controlled by `speed_v`).
       - `19`: Set the current preset bit (controlled by `speed_v`).

       Successful commands will control the device as requested and return an appropriate status message.
       """


@router.post(
    "/setPtzControl",
    response_model=SetPtzControlResponse,
    description=ptz_control_description,
)
async def set_ptz_control(device_id: str, request: SetPtzControl):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:8]
    message = {
        "request_type": "setPtzControl",
        "request_id": request_id,
        "pass": generate_md5(request.password),
        "channel": request.channel,
        "speed_h": request.speed_h,
        "speed_v": request.speed_v,
        "ptz_cmd": request.ptz_cmd,
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=20)
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


SetFaceConfig_description = """
```
SetFaceConfig callback data
{
    "request_id": number = unique id of each message generated by server,
    "pass": str = device password,
    "request_type": "SetFaceConfig",
    "FaceQuality": number[1, 10] = Face sensitivity, as high it is as sensitive is camera,
    "FaceTrackTnable": number[0, 1] = Enables face frame,
    "MaskDetectEnable": number[0, 1] = Enables mask detection if value is 1,
    "FaceMiniPixel": number[30, 300] = Minimum quantity of pixels that may contain face,
    "FaceMaxPixel": number[300, 700] = Maximum quantity of pixels that may contain face,
    "DaEnable": number[0, 1] = Enables face detection area if value is 1,
    "DetectAreaX": number[0, 1920] = X point of face detection area,
    "DetectAreaY": number[0, 1920] = Y point of face detection area,
    "DetectAreaW": number[0, 1920] = Width of face detection area,
    "DetectAreaH": number[0, 1920] = Height of face detection area,
    "LivenessEnable": number[0, 1] = Enables liveness 0:close  1:Color Detection,
    "LivenessThreshold": float[0, 0.99] = Living threshold,
    "SnapMode": [1, 5] = Capture mode 0: 'Snap After People Leave',
                                      1:'Fast+Snap After People Leave',
                                      2: 'numbererval Of Snap - Second Unit',
                                      3: 'numbererval Of Snap - Frame Unit',
                                      5: 'Snap After People Leave - Identify Priority'
    "IntervalFrame": number[10, 1500] = Interval frame ,
    "IntervalTime": [1, 30] = Interval time ,
    "SnapNum": [0, 16] = Number of Snapshots [0]: Unlimited  
    "UploadMode": number[0, 5] = Local Image Save Mode 0: 'Face Image',
                                                    1: 'Background Image',
                                                    2: 'Face&Background Image',
                                                    3: 'Face & Humanoid',
                                                    4:'Face&Humanoid&Background',
                                                    5: 'Humanoid Image',
    "ChooseMode": [0, 1] = Selection Mode 0: 'Quality',
                                          1: 'Point', 
    "Yaw": [0, 100] = Angle of face turning to left or right,
    "Pitch": [0, 100] = Face elevation angle,
    "Roll": [0, 100] = Head crooked roll angle,
    "FacePicQuality": number[0, 99] = Face picture quality,
    "PicQuality": number[0, 90] = scene picture quality,
    "SnapFaceArea": number[0, 10] = face image expansion factor,
    "MultiFace": number[0, 1] = face property detection mode,
    "BodyQuality": number[0, 90] = Humanoid Coding Quality,
    "BodyAreaEx": number[0, 10] = Humanoid expansion factor,
    "ExposureMode": number[0, 1] = Exposure mode 1:LIGHTER,
    "PicUploadMode": number = image upload mode 0001: face image
                                             0010: humanoid image,
                                             0100: background image, example to get all the code: 0111
    "WedIrMinFace": number = The light controls the smallest number of pixels of the face,
    "TempEnable": number[0, 1] = temperature mode,
    "CompEnable": number[0, 1] = Compare mode,
    "IoType": number[0, 1] = IO output type,
    "IOOutputTime": number[100, 60 000] = IO output time in ms,
    "AlarmTempValue": number[30, 40] = alarm temperature threshold in celsius,
    "TempDetectAreaX": number[0, 1920] = X point of temperature detection area,
    "TempDetectAreaY": number[0, 1920] = Y point of temperature detection area,
    "TempDetectAreaW": number[0, 1920] = Width of temperature detection area,
    "TempDetectAreaH": number[0, 1920] = Height of temperature detection area,
    "TempMinPixel": number[31, 1080] = temperature measurement of the smallest pixel of the face,
    "TempMaxPixel": number[31, 1080] = temperature measurement of the largest pixel of the face,
    "IoEnable": number[0, 1] = enable IO output,
    "ShowFaceName_N": number[0, 1] = show face name,
    "IoController": number[0, 5] = the type of io output trigger Whitelist:0,
                                                              Blacklist:1,
                                                              stranger:3,
                                                              VIP:4,
                                                              Whitelist 或 VIP:5
    "TempType": number[0, 1] = Alarm temperature type 0: celsius 1: Fahrenheit,
    "strangerFilt": number[0, 1] = stranger deduplication mode,
    "strangerDay": number[1, 30] = stranger deduplication day,
}

```
"""


@router.post("/SetFaceConfig", description=SetFaceConfig_description)
async def set_face_config(device_id: str, request: SetFaceConfig):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:8]
    message = {
        "request_type": "SetFaceConfig",
        "request_id": request_id,
        "pass": generate_md5(request.password),
        "FaceQuality": request.FaceQuality,
        "FaceTrackTnable": request.FaceTrackTnable,
        "MaskDetectEnable": request.MaskDetectEnable,
        "FaceMiniPixel": request.FaceMiniPixel,
        "FaceMaxPixel": request.FaceMaxPixel,
        "DaEnable": request.DaEnable,
        "DetectAreaX": request.DetectAreaX,
        "DetectAreaY": request.DetectAreaY,
        "DetectAreaW": request.DetectAreaW,
        "DetectAreaH": request.DetectAreaH,
        "LivenessEnable": request.LivenessEnable,
        "LivenessThreshold": request.LivenessThreshold,
        "SnapMode": request.SnapMode,
        "IntervalFrame": request.IntervalFrame,
        "IntervalTime": request.IntervalTime,
        "SnapNum": request.SnapNum,
        "UploadMode": request.UploadMode,
        "ChooseMode": request.ChooseMode,
        "Yaw": request.Yaw,
        "Pitch": request.Pitch,
        "Roll": request.Roll,
        "FacePicQuality": request.FacePicQuality,
        "PicQuality": request.PicQuality,
        "SnapFaceArea": request.SnapFaceArea,
        "MultiFace": request.MultiFace,
        "BodyQuality": request.BodyQuality,
        "BodyAreaEx": request.BodyAreaEx,
        "ExposureMode": request.ExposureMode,
        "PicUploadMode": request.PicUploadMode,
        "WedIrMinFace": request.WedIrMinFace,
        "TempEnable": request.TempEnable,
        "CompEnable": request.CompEnable,
        "CmpThreshold": request.CmpThreshold,
        "IoType": request.IoType,
        "IOOutputTime": request.IOOutputTime,
        "AlarmTempValue": request.AlarmTempValue,
        "TempDetectAreaX": request.TempDetectAreaX,
        "TempDetectAreaY": request.TempDetectAreaY,
        "TempDetectAreaW": request.TempDetectAreaW,
        "TempDetectAreaH": request.TempDetectAreaH,
        "TempMinPixel": request.TempMinPixel,
        "TempMaxPixel": request.TempMaxPixel,
        "IoEnable": request.IoEnable,
        "ShowFaceName_N": request.ShowFaceName_N,
        "IoController": request.IoController,
        "TempType": request.TempType,
        "strangerFilt": request.strangerFilt,
        "strangerDay": request.strangerDay,
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=20)
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


@router.post("/getFaceConfig")
async def get_face_config(device_id: str, request: GetFaceConfig):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:8]
    message = {
        "request_type": "GetFaceConfig",
        "request_id": request_id,
        "pass": generate_md5(request.password),
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=20)
        return response
    except TimeoutError as e:
        raise HTTPException(status_code=408, detail=str(e))


@router.post("/getFmtSnap")
async def get_fmt_snap(device_id: str, request: GetFmtSnap):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:8]
    message = {
        "request_type": "getFmtSnap",
        "request_id": request_id,
        "pass": generate_md5(request.password),
        "fmt": request.fmt,
    }
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=20)
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


@router.post("/getLogFile")
async def get_log_file(device_id: str, request: GetLogFile):
    try:
        websocket = manager.acquaintance_connections[device_id]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Device not found"
        )
    request_id = str(uuid4())[0:8]
    message = {
        "request_type": "getLogFile",
        "request_id": request_id,
        "pass": generate_md5(request.password),
        "log_name": request.log_name,
    }
    print(message)
    await manager.send_personal_message(json.dumps(message), websocket)
    try:
        response = await manager.wait_for_message(device_id, request_id, timeout=20)
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
