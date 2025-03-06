from fastapi import HTTPException, status
from sqlalchemy.orm.session import Session

from models import Schedule, ScheduleTemplate, Tenant, User, UserScheduleTemplate
from schemas.nvdsanalytics import (
    ScheduleTemplateBase,
    ScheduleTemplateCreate,
    ScheduleTemplateUpdate,
    UserScheduleTemplateBase,
)


def create_schedule_template(db: Session, data: ScheduleTemplateBase):
    schedule_template = ScheduleTemplate(name=data.name, description=data.description, tenant_id=data.tenant_id)
    db.add(schedule_template)
    db.commit()
    db.refresh(schedule_template)
    return schedule_template


def create_schedule_template_with_schedules(db: Session, data: ScheduleTemplateCreate):
    schedule_template = ScheduleTemplate(name=data.name, description=data.description, tenant_id=data.tenant_id)
    db.add(schedule_template)
    db.commit()
    db.refresh(schedule_template)
    for item in data.schedules:
        schedule = Schedule(
            template_id=schedule_template.id, weekday=item.weekday, start_time=item.start_time, end_time=item.end_time
        )
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
    return schedule_template


def get_schedule_templates(db: Session, tenant_id: int, is_active: bool = True):
    return db.query(ScheduleTemplate).filter_by(tenant_id=tenant_id, is_active=is_active)


def get_schedule_template(db: Session, template_id: int, is_active: bool = True):
    template = db.query(ScheduleTemplate).filter_by(id=template_id, is_active=is_active).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule Template not found")
    return template


def update_schedule_template(db: Session, template_id: int, data: ScheduleTemplateUpdate):
    tenant = db.query(Tenant).filter_by(id=data.tenant_id, is_active=True).first()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    template = db.query(ScheduleTemplate).filter_by(id=template_id, is_active=True).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    template.name = data.name
    if data.description:
        template.description = data.description
    template.tenant_id = data.tenant_id
    db.commit()
    db.refresh(template)
    for item in data.schedules:
        schedule = db.query(Schedule).filter_by(id=item.id, is_active=True).first()
        if not schedule:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found")
        if item.weekday:
            schedule.weekday = item.weekday
        if item.start_time:
            schedule.start_time = item.start_time
        if item.end_time:
            schedule.end_time = item.end_time
        db.commit()
        db.refresh(schedule)
    return template


def delete_schedule_template(db: Session, template_id: int):
    template = db.query(ScheduleTemplate).filter_by(id=template_id, is_active=True).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    template.is_active = False
    db.commit()
    db.refresh(template)
    return template


def create_user_schedule(db: Session, data: UserScheduleTemplateBase):
    user = db.query(User).filter_by(id=data.user_id, is_active=True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    template = db.query(ScheduleTemplate).filter_by(id=data.template_id, is_active=True).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    user_schedule = UserScheduleTemplate(user_id=data.user_id, template_id=data.template_id)
    db.add(user_schedule)
    db.commit()
    db.refresh(user_schedule)
    return user_schedule


def get_user_schedules(db: Session, user_id: int, is_active: bool = True):
    return db.query(UserScheduleTemplate).filter_by(user_id=user_id, is_active=is_active)


def get_schedule_users(db: Session, template_id: int, is_active: bool = True):
    return db.query(UserScheduleTemplate).filter_by(template_id=template_id, is_active=is_active)


def get_user_schedule(db: Session, pk: int, is_active: bool = True):
    user_schedule = db.query(UserScheduleTemplate).filter_by(id=pk, is_active=is_active).first()
    if not user_schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Schedule not found")
    return user_schedule


def update_user_schedule(db: Session, pk: int, data: UserScheduleTemplateBase):
    user = db.query(User).filter_by(id=data.user_id, is_active=True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    template = db.query(ScheduleTemplate).filter_by(id=data.template_id, is_active=True).first()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    user_schedule = db.query(UserScheduleTemplate).filter_by(id=pk, is_active=True).first()
    if not user_schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User Schedule not found")
    user_schedule.user_id = data.user_id
    user_schedule.template_id = data.template_id
    db.commit()
    db.refresh(user_schedule)
    return user_schedule


def delete_user_schedule(db: Session, pk: int):
    user_schedule = db.query(UserScheduleTemplate).filter_by(id=pk, is_active=True).first()
    if not user_schedule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User schedule not found")
    user_schedule.is_active = False
    db.commit()
    db.refresh(user_schedule)
    return user_schedule
