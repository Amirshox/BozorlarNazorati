import os

from fastapi import APIRouter, Depends, HTTPException, Security, status
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.orm import Session

from auth.oauth2 import get_current_tenant_admin
from database import db_wanted
from database.database import get_pg_db
from database.minio_client import get_minio_client
from models import Wanted
from schemas.wanted import WantedBase, WantedInDB, WantedUpdate
from utils.image_processing import get_image_from_query, make_minio_url_from_image
from utils.pagination import CustomPage

router = APIRouter(prefix="/wanted", tags=["wanted"])

WANTED_BUCKET = os.getenv("MINIO_BUCKET_WANTED", "wanted")
global_minio_client = get_minio_client()
if not global_minio_client.bucket_exists(WANTED_BUCKET):
    global_minio_client.make_bucket(WANTED_BUCKET)


@router.post("/", response_model=WantedInDB)
def create_wanted(
    data: WantedBase,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
    minio_client=Depends(get_minio_client),
):
    main_image = get_image_from_query(data.photo)
    main_photo_url = make_minio_url_from_image(minio_client, main_image, WANTED_BUCKET, is_check_hd=False)
    data.photo = main_photo_url
    wanted = db_wanted.create_wanted(db, data)
    # if data.tenant_entity_id:
    #     smart_cameras = db.query(SmartCamera).filter_by(tenant_entity_id=data.tenant_entity_id, is_active=True).all()
    #     for smart_camera in smart_cameras:
    #         add_wanted_to_smart_camera.delay(
    #             wanted.id,
    #             wanted.first_name,
    #             wanted.photo,
    #             wanted.concern_level,
    #             wanted.accusation,
    #             smart_camera.id,
    #             smart_camera.device_id,
    #             smart_camera.password,
    #             tenant_admin.tenant_id,
    #             data.tenant_entity_id,
    #         )
    return wanted


@router.get("/", response_model=CustomPage[WantedInDB])
def get_wanteds(db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)):
    query_set = db_wanted.get_wanteds(db, tenant_admin.tenant_id)
    return paginate(query_set)


@router.get("/by_entity", response_model=CustomPage[WantedInDB])
def get_entity_wanteds(
    tenant_entity_id: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    query_set = db_wanted.get_entity_wanteds(db, tenant_entity_id, tenant_admin.tenant_id)
    return paginate(query_set)


@router.get("/{pk}", response_model=WantedInDB)
def get_wanted(pk: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)):
    return db_wanted.get_wanted(db, pk)


@router.put("/{pk}", response_model=WantedInDB)
def update_wanted(
    pk: int,
    data: WantedBase,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
    minio_client=Depends(get_minio_client),
):
    wanted = db.query(Wanted).filter_by(id=pk, is_active=True).first()
    if not wanted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wanted not found")
    if wanted.photo != data.photo:
        main_image = get_image_from_query(data.photo)
        main_photo_url = make_minio_url_from_image(minio_client, main_image, WANTED_BUCKET, is_check_hd=False)
        data.photo = main_photo_url
    data = WantedUpdate(**data.__dict__)
    data.tenant_id = tenant_admin.tenant_id
    return db_wanted.update_wanted(db, pk, data)


@router.delete("/{pk}", response_model=WantedInDB)
def delete_wanted(pk: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)):
    return db_wanted.delete_wanted(db, pk)
