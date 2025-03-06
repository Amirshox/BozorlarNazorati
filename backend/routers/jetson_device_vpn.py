import os
import re
import tempfile

from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi.responses import FileResponse
from jinja2 import Environment, FileSystemLoader
from minio import Minio
from sqlalchemy.orm import Session

from auth.oauth2 import get_current_tenant_admin
from database.database import get_pg_db
from database.minio_client import get_minio_client
from models import JetsonDevice, JetsonDeviceVPNCredentials
from schemas.jetson_device_vpn import OpenVPNSetUpConfigs

router = APIRouter(prefix="/openvpn", tags=["openvpn"])

template_dir = os.path.abspath(os.path.dirname(__file__))
jinja_env = Environment(loader=FileSystemLoader(template_dir))


def get_jetson_device_vpn_credentials(jetson_device_id: int, db: Session, minio_client: Minio):
    jetson_device = db.query(JetsonDevice).filter_by(id=jetson_device_id).first()

    if not jetson_device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"JetsonDevice with specified id({jetson_device_id}) not found",
        )

    vpn_credentials = db.query(JetsonDeviceVPNCredentials).filter_by(jetson_device_id=jetson_device_id).first()

    if not vpn_credentials:
        last_vpn_credential = (
            db.query(JetsonDeviceVPNCredentials).order_by(JetsonDeviceVPNCredentials.created_at.desc()).first()
        )

        client_certifcate = "jetson-g-1.crt"
        client_key = "jetson-g-1.key"

        if last_vpn_credential:
            last_cert_index = int(re.findall(r"\d+", last_vpn_credential.client_certificate)[0])
            last_key_index = int(re.findall(r"\d+", last_vpn_credential.client_key)[0])

            client_certifcate = f"jetson-g-{last_cert_index + 1}.crt"
            client_key = f"jetson-g-{last_key_index + 1}.key"

        created_vpn_credentials = JetsonDeviceVPNCredentials(
            jetson_device_id=jetson_device_id, client_certificate=client_certifcate, client_key=client_key
        )

        db.add(created_vpn_credentials)
        db.commit()
        db.refresh(created_vpn_credentials)

        client_certificate_response = minio_client.get_object(
            "vpncredentials", f"issued/{created_vpn_credentials.client_certificate}"
        )
        client_key_response = minio_client.get_object("vpncredentials", f"private/{created_vpn_credentials.client_key}")

        client_certificate_content = client_certificate_response.read().decode("utf-8")
        client_certificate_response.close()

        client_key_content = client_key_response.read().decode("utf-8")
        client_key_response.close()

        return {"cert": client_certificate_content, "key": client_key_content}
    else:
        client_certificate_response = minio_client.get_object(
            "vpncredentials", f"issued/{vpn_credentials.client_certificate}"
        )
        client_key_response = minio_client.get_object("vpncredentials", f"private/{vpn_credentials.client_key}")

        client_certificate_content = client_certificate_response.read().decode("utf-8")
        client_certificate_response.close()

        client_key_content = client_key_response.read().decode("utf-8")
        client_key_response.close()

        return {"cert": client_certificate_content, "key": client_key_content}


@router.post("/setup_config")
def create_open_vpn_config_set_up_file(
    set_up_file: OpenVPNSetUpConfigs,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
    minio_client: Minio = Depends(get_minio_client),
):
    credentials = get_jetson_device_vpn_credentials(set_up_file.jetson_device_id, db=db, minio_client=minio_client)

    with open("routers/setup_payload/ca.crt") as file:
        ca_certififcate = file.read()

    template = jinja_env.get_template("setup_payload/vpn_setup.sh")
    rendered_shell_script = template.render(
        vpn_server=set_up_file.vpn_server,
        vpn_port=set_up_file.vpn_port,
        vpn_protocol=set_up_file.vpn_protocol,
        ca_certificate=ca_certififcate,
        client_certificate=credentials["cert"],
        client_key=credentials["key"],
    )

    temporary_file = tempfile.NamedTemporaryFile(delete=False, suffix=".sh")
    with open(temporary_file.name, "w") as created_file:
        created_file.write(rendered_shell_script)

    return FileResponse(temporary_file.name, media_type="application/x-sh", filename="vpn_setup.sh")
