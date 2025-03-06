from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from auth.oauth2 import get_current_tenant_admin
from database import nvdsanalytics
from database.database import get_pg_db
from schemas.nvdsanalytics import CreateRoiRequest, LineBase, LineInDB, LineUpdate, RoiInDB, RoiPointUpdate

router = APIRouter(prefix="/nvdsanalytics", tags=["nvdsanalytics"])


@router.post("/roi", response_model=RoiInDB)
def create_roi_points(
    data: CreateRoiRequest, db: Session = Depends(get_pg_db), tenant_admin=Depends(get_current_tenant_admin)
):
    return nvdsanalytics.create_roi_points(db, data)


@router.get("/roi", response_model=List[RoiInDB])
def get_roi_points(
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Depends(get_current_tenant_admin),
):
    return nvdsanalytics.get_rois(db, is_active)


@router.put("/roi/{pk}", response_model=RoiInDB)
def update_roi(
    pk: int, data: RoiPointUpdate, db: Session = Depends(get_pg_db), tenant_admin=Depends(get_current_tenant_admin)
):
    return nvdsanalytics.update_roi(db, pk, data)


@router.delete("/roi/{pk}", response_model=RoiInDB)
def delete_roi(pk: int, db: Session = Depends(get_pg_db), tenant_admin=Depends(get_current_tenant_admin)):
    return nvdsanalytics.delete_roi(db, pk)


@router.post("/line", response_model=LineInDB)
def create_line_points(
    data: LineBase, db: Session = Depends(get_pg_db), tenant_admin=Depends(get_current_tenant_admin)
):
    return nvdsanalytics.create_line_points(db, data)


@router.put("/line/{pk}", response_model=LineInDB)
def update_line(
    pk: int, data: LineUpdate, db: Session = Depends(get_pg_db), tenant_admin=Depends(get_current_tenant_admin)
):
    return nvdsanalytics.update_line(db, pk, data)


@router.delete("/line/{pk}", response_model=LineInDB)
def delete_line(pk: int, db: Session = Depends(get_pg_db), tenant_admin=Depends(get_current_tenant_admin)):
    return nvdsanalytics.delete_line(db, pk)


@router.get("/camera/{camera_id}/lines", response_model=List[LineInDB])
def get_line_points(
    camera_id: int,
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Depends(get_current_tenant_admin),
):
    return nvdsanalytics.get_camera_lines(db, camera_id, is_active)


@router.get("/camera/{camera_id}/points", response_model=List[RoiInDB])
def get_camera_points(
    camera_id: int,
    is_active: Optional[bool] = Query(True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    tenant_admin=Depends(get_current_tenant_admin),
):
    return nvdsanalytics.get_camera_rois(db, camera_id, is_active)
