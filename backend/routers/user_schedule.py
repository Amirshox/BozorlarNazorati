from typing import Optional
from sqlalchemy.orm import Session
from database import user_schedule
from database.database import get_pg_db
from utils.pagination import CustomPage
from auth.oauth2 import get_current_tenant_admin
from fastapi_pagination.ext.sqlalchemy import paginate
from fastapi import APIRouter, Depends, Query, HTTPException, status
from schemas.nvdsanalytics import (
    ScheduleTemplateBase, ScheduleTemplateInDB, ScheduleTemplateCreate, ScheduleTemplateUpdate,
    UserScheduleTemplateInDB, UserScheduleTemplateBase
)

router = APIRouter(prefix='/schedules', tags=['schedules'])


@router.post('/template', response_model=ScheduleTemplateInDB)
def create_schedule_template(
        template: ScheduleTemplateBase,
        db: Session = Depends(get_pg_db),
        tenant_admin=Depends(get_current_tenant_admin)
):
    try:
        return user_schedule.create_schedule_template(db, template)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post('/template/with_schedules', response_model=ScheduleTemplateInDB)
def create_schedule_template_with_schedules(
        template: ScheduleTemplateCreate,
        db: Session = Depends(get_pg_db),
        tenant_admin=Depends(get_current_tenant_admin)
):
    try:
        return user_schedule.create_schedule_template_with_schedules(db, template)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get('/template/by_tenant', response_model=CustomPage[ScheduleTemplateInDB])
def get_schedule_templates_by_tenant(
        tenant_id: int,
        is_active: Optional[bool] = Query(True, alias='is_active'),
        db: Session = Depends(get_pg_db),
        tenant_admin=Depends(get_current_tenant_admin)
):
    query_set = user_schedule.get_schedule_templates(db, tenant_id, is_active)
    return paginate(query_set)


@router.get('/template/{template_id}', response_model=ScheduleTemplateInDB)
def get_schedule_template(
        template_id: int,
        is_active: Optional[bool] = Query(True, alias='is_active'),
        db: Session = Depends(get_pg_db),
        tenant_admin=Depends(get_current_tenant_admin)
):
    return user_schedule.get_schedule_template(db, template_id, is_active)


@router.put('/template/{template_id}', response_model=ScheduleTemplateInDB)
def update_schedule_template(
        template_id: int,
        template: ScheduleTemplateUpdate,
        db: Session = Depends(get_pg_db),
        tenant_admin=Depends(get_current_tenant_admin)
):
    return user_schedule.update_schedule_template(db, template_id, template)


@router.delete('/template/{template_id}', response_model=ScheduleTemplateInDB)
def delete_schedule_template(
        template_id: int,
        db: Session = Depends(get_pg_db),
        tenant_admin=Depends(get_current_tenant_admin)
):
    return user_schedule.delete_schedule_template(db, template_id)


@router.post('/user', response_model=UserScheduleTemplateInDB)
def create_user_schedule(
        data: UserScheduleTemplateBase,
        db: Session = Depends(get_pg_db),
        tenant_admin=Depends(get_current_tenant_admin)
):
    try:
        return user_schedule.create_user_schedule(db, data)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get('/user/schedules', response_model=CustomPage[UserScheduleTemplateInDB])
def get_user_schedule(
        user_id: int,
        is_active: Optional[bool] = Query(True, alias='is_active'),
        db: Session = Depends(get_pg_db),
        tenant_admin=Depends(get_current_tenant_admin)
):
    query_set = user_schedule.get_user_schedule(db, user_id, is_active)
    return paginate(query_set)


@router.get('/schedule/users', response_model=CustomPage[UserScheduleTemplateInDB])
def get_schedule_users(
        template_id: int,
        is_active: Optional[bool] = Query(True, alias='is_active'),
        db: Session = Depends(get_pg_db),
        tenant_admin=Depends(get_current_tenant_admin)
):
    query_set = user_schedule.get_schedule_users(db, template_id, is_active)
    return paginate(query_set)


@router.get('/user/{pk}', response_model=UserScheduleTemplateInDB)
def get_user_schedule(
        pk: int,
        is_active: Optional[bool] = Query(True, alias='is_active'),
        db: Session = Depends(get_pg_db),
        tenant_admin=Depends(get_current_tenant_admin)
):
    return user_schedule.get_user_schedule(db, pk, is_active)


@router.put('/user/{pk}', response_model=UserScheduleTemplateInDB)
def update_user_schedule(
        pk: int,
        data: UserScheduleTemplateBase,
        db: Session = Depends(get_pg_db),
        tenant_admin=Depends(get_current_tenant_admin)
):
    return user_schedule.update_user_schedule(db, pk, data)


@router.delete('/user/{pk}', response_model=UserScheduleTemplateInDB)
def delete_user_schedule(
        pk: int,
        db: Session = Depends(get_pg_db),
        tenant_admin=Depends(get_current_tenant_admin)
):
    return user_schedule.delete_user_schedule(db, pk)
