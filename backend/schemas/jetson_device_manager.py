from typing import Any, List

from pydantic import BaseModel


class BaseRequest(BaseModel):
    application_name: str
    application_version: str
    jetson_device_id: str


class AddDeepstreamApplicationRequest(BaseRequest):
    application_github_url: str


class RunDeepstreamApplicationRequest(BaseRequest):
    pass


class StopDeeepstreamApplicationRequest(BaseRequest):
    pass


class EnlistDeepstreamApplication(BaseModel):
    jetson_device_id: str


class EnlistApplicationConfigurations(BaseRequest):
    pass


class GetSnapshot(BaseModel):
    camera_id: int
    jetson_device_id: str
    rtsp_connection_url: str


class GetCameras(BaseModel):
    jetson_device_id: str
    scanning_network: str


class GetNetworks(BaseModel):
    jetson_device_id: str


class UpdateDeepstreamAppRequest(BaseRequest):
    pass


class ConfigUpdateAddGroup(BaseRequest):
    config_file_name: str
    config_group_name: str
    group_properties: Any


class ConfigUpdateRemoveGroup(BaseRequest):
    config_file_name: str
    config_group_name: str


class ConfigUpdateAddProperty(BaseRequest):
    config_file_name: str
    config_group_name: str
    config_property_name: str
    config_property_value: Any


class ConfigUpdateReplaceProperty(BaseRequest):
    config_file_name: str
    config_group_name: str
    config_property_name: str
    config_property_value: Any


class ConfigUpdateRemoveProperty(BaseRequest):
    config_file_name: str
    config_group_name: str
    config_property_name: Any


class UpdateDeepstreamAppCameras(BaseRequest):
    camera_rtsp_urls: List[str]


class DeepstreamRoi(BaseModel):
    roi_id: int
    coordinates: List[int]


class DeepstreamLine(BaseModel):
    line_id: int
    coordinates: List[int]


class DeepstreamRoiStream(BaseModel):
    rois: List[DeepstreamRoi]


class LineCrossingStream(BaseModel):
    lines: List[DeepstreamLine]


class UpdateDeepstreamAppRoiStream(BaseRequest):
    streams: List[DeepstreamRoiStream]


class UpdateDeepstreamAppLineCrossingStream(BaseRequest):
    streams: List[LineCrossingStream]
