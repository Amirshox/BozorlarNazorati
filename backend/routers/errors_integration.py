from typing import Optional
from sqlalchemy.orm import Session
from database import db_smartcamera
from utils.pagination import CustomPage
from database.database import get_pg_db
from fastapi import APIRouter, Depends, Query
from auth.oauth2 import get_current_tenant_admin
from fastapi_pagination.ext.sqlalchemy import paginate
from schemas.nvdsanalytics import ErrorSmartCameraBase, ErrorSmartCameraInDB

router = APIRouter(prefix='/errors_integration', tags=['errors_integration'])


@router.get('/error_by_scamera/{smart_camera_id}', response_model=CustomPage[ErrorSmartCameraInDB])
def get_errors_by_smart_camera_id(
        smart_camera_id: int,
        is_active: Optional[bool] = Query(default=True, alias='is_active'),
        db: Session = Depends(get_pg_db),
        tenant_admin=Depends(get_current_tenant_admin)
):
    query_set = db_smartcamera.get_errors_by_scamera(db, smart_camera_id, is_active)
    return paginate(query_set)


@router.get('/error_by_user/{user_id}', response_model=CustomPage[ErrorSmartCameraInDB])
def get_errors_by_user_id(
        user_id: int,
        is_active: Optional[bool] = Query(default=True, alias='is_active'),
        db: Session = Depends(get_pg_db),
        tenant_admin=Depends(get_current_tenant_admin)
):
    query_set = db_smartcamera.get_errors_by_user(db, user_id, is_active)
    return paginate(query_set)


@router.get('/error_by_identity/{identity_id}', response_model=CustomPage[ErrorSmartCameraInDB])
def get_errors_by_identity_id(
        identity_id: int,
        is_active: Optional[bool] = Query(default=True, alias='is_active'),
        db: Session = Depends(get_pg_db),
        tenant_admin=Depends(get_current_tenant_admin)
):
    query_set = db_smartcamera.get_errors_by_identity(db, identity_id, is_active)
    return paginate(query_set)


@router.get('/error/all', response_model=CustomPage[ErrorSmartCameraInDB])
def get_all_errors(
        is_resolved: Optional[bool] = Query(default=False, alias='is_resolved'),
        is_active: Optional[bool] = Query(default=True, alias='is_active'),
        db: Session = Depends(get_pg_db),
        tenant_admin=Depends(get_current_tenant_admin)
):
    query_set = db_smartcamera.get_errors(db, is_resolved, is_active)
    return paginate(query_set)


@router.get('/error/{pk}', response_model=ErrorSmartCameraInDB)
def get_error_smart_camera(
        pk: int,
        is_active: Optional[bool] = Query(default=True, alias='is_active'),
        db: Session = Depends(get_pg_db),
        tenant_admin=Depends(get_current_tenant_admin)
):
    return db_smartcamera.get_error_smart_camera(db, pk, is_active)


@router.put('/error/{pk}', response_model=ErrorSmartCameraInDB)
def update_error_smart_camera(
        pk: int,
        data: ErrorSmartCameraBase,
        db: Session = Depends(get_pg_db),
        tenant_admin=Depends(get_current_tenant_admin)
):
    return db_smartcamera.update_error_scamera(db, pk, data)


@router.delete('/error/{pk}', response_model=ErrorSmartCameraInDB)
def delete_error_smart_camera(
        pk: int,
        db: Session = Depends(get_pg_db),
        tenant_admin=Depends(get_current_tenant_admin)
):
    return db_smartcamera.delete_error_scamera(db, pk)
