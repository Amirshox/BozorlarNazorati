from typing import Literal

from pydantic import BaseModel


class OpenVPNSetUpConfigs(BaseModel):
    vpn_server: str
    vpn_protocol: Literal["tcp", "udp"]
    vpn_port: str
    jetson_device_id: int
