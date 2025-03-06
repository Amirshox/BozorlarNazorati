import os
import uuid

from fastapi import APIRouter, Depends, File, Security, UploadFile

from auth.oauth2 import get_current_sysadmin
from database.minio_client import get_minio_client
from utils.generator import generate_md5

from config import MINIO_PROTOCOL, MINIO_HOST

BUCKET_NAME = "filestorage"
BUCKET_DOCUMENTATION = "documentation"

global_minio_client = get_minio_client()
if not global_minio_client.bucket_exists(BUCKET_NAME):
    global_minio_client.make_bucket(BUCKET_NAME)
if not global_minio_client.bucket_exists(BUCKET_DOCUMENTATION):
    global_minio_client.make_bucket(BUCKET_DOCUMENTATION)

router = APIRouter(prefix="/file_manager", tags=["file_manager"])


@router.get("/get_presigned_url")
async def get_presigned_url(file_name: str, minio_client=Depends(get_minio_client)):
    try:
        presigned_url = minio_client.presigned_put_object(BUCKET_NAME, file_name)
        return {"presigned_url": presigned_url}
    except Exception as e:
        return {"error": str(e)}


@router.post("/upload_file")
async def upload_file(file: UploadFile = File(...), minio_client=Depends(get_minio_client)):
    try:
        unique_id = str(uuid.uuid4())
        file_extension = file.filename.split(".")[-1]
        file_name = f"{await generate_md5(unique_id)}.{file_extension}"
        image = file.file.read()
        file.file.seek(0)
        minio_client.put_object(BUCKET_NAME, file_name, file.file, len(image))
        return {"file_name": file_name, "file_url": f"{MINIO_PROTOCOL}://{MINIO_HOST}/{BUCKET_NAME}/{file_name}"}
    except Exception as e:
        return {"error": str(e)}


@router.post("/upload/documentation")
async def upload_documentation(
    file: UploadFile = File(...), sysadmin=Security(get_current_sysadmin), minio_client=Depends(get_minio_client)
):
    try:
        uniqi_id = str(uuid.uuid4())
        file_extension = file.filename.split(".")[-1]
        file_name = f"{await generate_md5(uniqi_id)}.{file_extension}"
        image = file.file.read()
        file.file.seek(0)
        minio_client.put_object(BUCKET_DOCUMENTATION, file_name, file.file, len(image))
        return {
            "file_name": file_name,
            "file_url": f"{MINIO_PROTOCOL}://{MINIO_HOST}/{BUCKET_DOCUMENTATION}/{file_name}",
        }
    except Exception as e:
        return {"error": str(e)}
