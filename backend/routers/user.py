import os
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Security
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy.orm import Session

from auth.oauth2 import get_current_tenant_admin
from database import db_user, db_user_activation_code, db_user_smart_camera
from database.database import get_pg_db
from database.minio_client import get_minio_client
from schemas.shared import RoleInDBBase
from schemas.user import UserBase, UserCreate, UserInDBBase, UserSmartCameraBase, UserSmartCameraInDB, UserUpdate
from utils import generator
from utils.image_processing import get_image_from_query, make_minio_url_from_image
from utils.pagination import CustomPage

router = APIRouter(prefix="/user", tags=["user"])

USER_BUCKET = os.getenv("MINIO_BUCKET_USER", "user")

CAMERA_MANAGER_URL = os.getenv("CAMERA_MANAGER_URL")
CAMERA_MANAGER_BASIC = os.getenv("CAMERA_MANAGER_BASIC")
CAMERA_MANAGER_PASSWORD = os.getenv("CAMERA_MANAGER_PASSWORD")

global_minio_client = get_minio_client()
if not global_minio_client.bucket_exists(USER_BUCKET):
    global_minio_client.make_bucket(USER_BUCKET)


@router.post("/", response_model=UserInDBBase)
def create_user(
    user: UserCreate,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
    minio_client=Depends(get_minio_client),
):
    if user.photo:
        main_image = get_image_from_query(user.photo)
        main_photo_url = make_minio_url_from_image(minio_client, main_image, USER_BUCKET)
        user.photo = main_photo_url
    if user.cropped_image:
        cropped_image = get_image_from_query(user.cropped_image)
        cropped_photo_url = make_minio_url_from_image(minio_client, cropped_image, USER_BUCKET, is_check_size=False)
        user.cropped_image = cropped_photo_url
    if user.cropped_image512:
        cropped_image512 = get_image_from_query(user.cropped_image512)
        cropped_photo512_url = make_minio_url_from_image(
            minio_client, cropped_image512, USER_BUCKET, is_check_size=False
        )
        user.cropped_image512 = cropped_photo512_url
    return db_user.create_tenant_entity_user(db, tenant_admin.tenant_id, user)


@router.get("/roles", response_model=List[RoleInDBBase])
def get_user_roles(db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)):
    return db_user.get_user_roles(db, tenant_admin.tenant_id)


@router.get("/", response_model=CustomPage[UserInDBBase])
def get_tenant_users(
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    query_set = db_user.get_tenant_users(db, tenant_admin.tenant_id, is_active)
    return paginate(query_set)


@router.get("/by_camera/{camera_id}", response_model=CustomPage[UserInDBBase])
def get_users_by_camera(
    camera_id: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    query_set = db_user.get_users_by_camera(db, camera_id)
    return paginate(query_set)


@router.get("/by_smart_camera", response_model=CustomPage[UserInDBBase])
def get_users_by_smart_camera(
    smart_camera_id: int,
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return paginate(db_user.get_users_by_scamera_id(db, smart_camera_id, is_active))


@router.get("/tenant_entity/{tenant_entity_id}", response_model=CustomPage[UserInDBBase])
def get_tenant_entity_users(
    tenant_entity_id: int,
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    query_set = db_user.get_tenant_entity_users(db, tenant_admin.tenant_id, tenant_entity_id, is_active)
    return paginate(query_set)


@router.get("/{pk}", response_model=UserInDBBase)
def get_user(
    pk: int,
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_user.get_tenant_entity_user(db, tenant_admin.tenant_id, pk, is_active)


@router.put("/{pk}", response_model=UserInDBBase)
def update_user(
    pk: int,
    user: UserUpdate,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
    minio_client=Depends(get_minio_client),
):
    if user.photo:
        main_image = get_image_from_query(user.photo)
        main_photo_url = make_minio_url_from_image(minio_client, main_image, USER_BUCKET)
        user.photo = main_photo_url
    if user.cropped_image:
        cropped_image = get_image_from_query(user.cropped_image)
        cropped_photo_url = make_minio_url_from_image(minio_client, cropped_image, USER_BUCKET, is_check_size=False)
        user.cropped_image = cropped_photo_url
    if user.cropped_image512:
        cropped_image512 = get_image_from_query(user.cropped_image512)
        cropped_photo512_url = make_minio_url_from_image(
            minio_client, cropped_image512, USER_BUCKET, is_check_size=False
        )
        user.cropped_image512 = cropped_photo512_url
    return db_user.update_tenant_user(db, tenant_admin.tenant_id, pk, user)


@router.post("/create_in_active", response_model=UserInDBBase)
async def create_user_in_active(
    user: UserBase,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
    minio_client=Depends(get_minio_client),
):
    if user.photo:
        main_image = get_image_from_query(user.photo)
        main_photo_url = make_minio_url_from_image(minio_client, main_image, USER_BUCKET)
        user.photo = main_photo_url
    if user.cropped_image:
        cropped_image = get_image_from_query(user.cropped_image)
        cropped_photo_url = make_minio_url_from_image(minio_client, cropped_image, USER_BUCKET, is_check_size=False)
        user.cropped_image = cropped_photo_url
    if user.cropped_image512:
        cropped_image512 = get_image_from_query(user.cropped_image512)
        cropped_photo512_url = make_minio_url_from_image(
            minio_client, cropped_image512, USER_BUCKET, is_check_size=False
        )
        user.cropped_image512 = cropped_photo512_url
    in_active_user = db_user.create_inactive_tenant_entity_user(db, tenant_admin.tenant_id, user)
    generated_token = generator.generate_token(length=32)
    db_user_activation_code.create_activation_code(db, in_active_user.id, generated_token)
    return in_active_user


@router.post("/activate")
def activate_user(code: str, new_password: str, db: Session = Depends(get_pg_db)):
    return db_user_activation_code.get_activation_code_and_update_password(db, code, new_password)


@router.delete("/{pk}", response_model=UserInDBBase)
def delete_user(pk: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)):
    return db_user.delete_tenant_user(db, tenant_admin.tenant_id, pk)


@router.post("/smartcamera", response_model=UserSmartCameraInDB)
def add_user_to_smartcamera(
    user_smartcamera: UserSmartCameraBase,
    db: Session = Depends(get_pg_db),
    tenant_admin=Security(get_current_tenant_admin),
):
    return db_user_smart_camera.create_user_smart_camera(db, user_smartcamera)


@router.delete("/smartcamera/{pk}", response_model=UserSmartCameraInDB)
def delete_user_from_smartcamera(
    pk: int, db: Session = Depends(get_pg_db), tenant_admin=Security(get_current_tenant_admin)
):
    return db_user_smart_camera.delete_user_smart_camera(db, pk)
