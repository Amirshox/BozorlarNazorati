from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy.orm.session import Session

from models import Camera, Identity, Line, Roi, RoiLabel, RoiPoint, SmartCamera
from schemas.nvdsanalytics import CreateRoiRequest, LineBase, LineUpdate, RoiBase


def get_roi(db: Session, pk: int):
    return db.query(Roi).filter_by(id=pk).first()


def create_roi_points(db: Session, data: CreateRoiRequest):
    roi = Roi(
        name=data.name,
        color=data.color,
        description=data.description,
        identity_id=data.identity_id,
        workspace_type=data.workspace_type,
        people_count_threshold=data.people_count_threshold,
        safe_zone_start_time=data.safe_zone_start_time,
        safe_zone_end_time=data.safe_zone_end_time,
        camera_id=data.camera_id,
        smart_camera_id=data.smart_camera_id,
        detection_object_type=data.detection_object_type
    )

    db.add(roi)
    db.commit()
    db.refresh(roi)

    for each_label in data.labels:
        roi_lable = RoiLabel(roi_id=roi.id, label_title=each_label)

        db.add(roi_lable)
        db.commit()
        db.refresh(roi_lable)

    for item in data.points:
        point = RoiPoint(x=item.x, y=item.y, order_number=item.order_number, roi_id=roi.id)
        db.add(point)
        db.commit()
        db.refresh(point)

    db.refresh(roi)

    return roi


def get_rois(db: Session, is_active: bool = True):
    return db.query(Roi).filter_by(is_active=is_active).all()


def delete_roi(db: Session, pk: int):
    roi = db.query(Roi).filter_by(id=pk, is_active=True).first()
    if not roi:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Roi does not exist")
    roi.is_active = False
    db.commit()
    db.refresh(roi)
    return roi


def update_roi(db: Session, pk, data: RoiBase):
    identity_exists = db.query(Identity).filter_by(id=data.identity_id, is_active=True).first()
    if not identity_exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User does not exist")
    if data.camera_id:
        camera_exists = db.query(Camera).filter_by(id=data.camera_id, is_active=True).first()
        if not camera_exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Camera does not exist")
    if data.smart_camera_id:
        smart_camera_exists = db.query(SmartCamera).filter_by(id=data.smart_camera_id, is_active=True).first()
        if not smart_camera_exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Smart camera does not exist")
    roi = db.query(Roi).filter_by(id=pk, is_active=True).first()
    if not roi:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Roi does not exist")
    if data.name:
        roi.name = data.name
    if data.description:
        roi.description = data.description
    if data.identity_id:
        roi.identity_id = data.identity_id
    if data.color:
        roi.color = data.color
    if data.camera_id:
        roi.camera_id = data.camera_id
    if data.smart_camera_id:
        roi.smart_camera_id = data.smart_camera_id
    db.commit()
    db.refresh(roi)
    for item in data.points:
        point = db.query(RoiPoint).filter_by(id=item.id, roi_id=roi.id, is_active=True).first()
        if point:
            point.x = item.x
            point.y = item.y
            point.order_number = item.order_number
            db.commit()
            db.refresh(point)
    return roi


def create_line_points(db: Session, data: LineBase):
    if data.camera_id:
        camera_exists = db.query(Camera).filter_by(id=data.camera_id, is_active=True).first()
        if not camera_exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Camera does not exist")
    if data.smart_camera_id:
        smart_camera_exists = db.query(SmartCamera).filter_by(id=data.smart_camera_id, is_active=True).first()
        if not smart_camera_exists:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Smart camera does not exist")
    if not data.camera_id and not data.smart_camera_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Camera and Smart camera does not exist")

    line = Line(
        name=data.name,
        description=data.description,
        type=data.type,
        camera_id=data.camera_id,
        smart_camera_id=data.smart_camera_id,
        dx1=data.dx1,
        dy1=data.dy1,
        dx2=data.dx2,
        dy2=data.dy2,
        x1=data.x1,
        y1=data.y1,
        x2=data.x2,
        y2=data.y2,
    )
    db.add(line)
    db.commit()
    db.refresh(line)
    return line


def update_line(db: Session, pk: int, data: LineUpdate):
    if data.camera_id:
        camera = db.query(Camera).filter_by(id=data.camera_id, is_active=True).first()
        if not camera:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Camera does not exist")
    elif data.smart_camera_id:
        smart_camera = db.query(SmartCamera).filter_by(id=data.smart_camera_id, is_active=True).first()
        if not smart_camera:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Smart camera does not exist")
    line = db.query(Line).filter_by(id=pk, is_active=True).first()
    if not line:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Line does not exist")
    if data.name:
        line.name = data.name
    if data.description:
        line.description = data.description
    if data.type:
        line.type = data.type
    if data.dx1:
        line.dx1 = data.dx1
    if data.dy1:
        line.dy1 = data.dy1
    if data.dx2:
        line.dx2 = data.dx2
    if data.dy2:
        line.dy2 = data.dy2
    if data.x1:
        line.x1 = data.x1
    if data.y1:
        line.y1 = data.y1
    if data.x2:
        line.x2 = data.x2
    if data.y2:
        line.y2 = data.y2
    if data.camera_id:
        line.camera_id = data.camera_id
    elif data.smart_camera_id:
        line.smart_camera_id = data.smart_camera_id
    db.commit()
    db.refresh(line)
    return line


def delete_line(db: Session, pk: int):
    line = db.query(Line).filter_by(id=pk, is_active=True).first()
    if not line:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Line does not exist")
    line.is_active = False
    db.commit()
    db.refresh(line)
    return line


def get_camera_lines(db: Session, camera_id: int, is_active: bool = True):
    return db.query(Line).filter_by(camera_id=camera_id, is_active=is_active).all()


def get_camera_rois(db: Session, camera_id: int, is_active: bool = True, is_safe_zone: bool = False):
    if is_safe_zone:
        all_rois = db.query(Roi).filter_by(camera_id=camera_id, is_active=is_active).all()
        safe_zone_rois = []

        for each_roi in all_rois:
            for each_lable in each_roi.labels:
                if each_lable.label_title == "safe-zone":
                    safe_zone_rois.append(each_roi)
        return safe_zone_rois
    else:
        return db.query(Roi).filter_by(camera_id=camera_id, is_active=is_active).all()


def get_identity_rois(
    db: Session,
    identity_id: int,
    roi_label: Literal["work-analytics", "safe-zone", "overcrowd-detection"],
    is_active: bool = True,
):
    filtered_identity_rois = []
    identity_rois = db.query(Roi).filter_by(identity_id=identity_id, is_active=is_active).all()

    for identity_roi in identity_rois:
        for each_lable in identity_roi.labels:
            if each_lable.label_title == roi_label:
                filtered_identity_rois.append(identity_roi)

    return filtered_identity_rois
