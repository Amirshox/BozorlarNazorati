from fastapi import HTTPException, status
from sqlalchemy import and_, func
from sqlalchemy.orm.session import Session

from models import Country, District, Region, TenantEntity
from schemas.region import CountryBase, DistrictBase, RegionBase


# -----------------------------Country---------------------------------
def create_country(db: Session, data: CountryBase):
    exist_country = db.query(Country).filter_by(name=data.name).first()
    if exist_country:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Country {data.name} already exists")
    country = Country(name=data.name)
    db.add(country)
    db.commit()
    db.refresh(country)
    return country


def update_country(db: Session, pk, data: CountryBase):
    exist_country = db.query(Country).filter_by(name=data.name).first()
    if exist_country and exist_country.id != pk:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Country {data.name} already exists")
    country = db.query(Country).filter_by(id=pk, is_active=True).first()
    if not country:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Country not found")
    country.name = data.name
    db.commit()
    db.refresh(country)
    return country


def get_countries(db: Session, is_active: bool = True):
    return db.query(Country).filter_by(is_active=is_active).all()


def get_country(db: Session, pk: int, is_active: bool = True):
    country = db.query(Country).filter_by(id=pk, is_active=is_active).first()
    if not country:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Country not found")
    return country


def delete_country(db: Session, pk: int):
    country = db.query(Country).filter_by(id=pk, is_active=True).first()
    if not country:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Country not found")
    country.is_active = False
    db.commit()
    db.refresh(country)
    return country


def search_country(db: Session, search_name: str):
    search_name_lower = f"%{search_name.lower()}%"
    return db.query(Country).filter(func.lower(Country.name).ilike(search_name_lower)).first()


# -----------------------------Country---------------------------------


# -----------------------------Region---------------------------------
def create_region(db: Session, data: RegionBase):
    exist_region = db.query(Region).filter_by(name=data.name, country_id=data.country_id).first()
    if exist_region:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Region already exists")
    country = db.query(Country).filter_by(id=data.country_id, is_active=True).first()
    if not country:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Country not found")
    region = Region(name=data.name, country_id=data.country_id)
    db.add(region)
    db.commit()
    db.refresh(region)
    return region


def update_region(db: Session, pk: int, data: RegionBase):
    exist_region = db.query(Region).filter_by(name=data.name, country_id=data.country_id).first()
    if exist_region and exist_region.id != pk:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Region already exists")
    country = db.query(Country).filter_by(id=data.country_id, is_active=True).first()
    if not country:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Country not found")
    region = db.query(Region).filter_by(id=pk, is_active=True).first()
    if not region:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Region not found")
    region.name = data.name
    region.country_id = data.country_id
    db.commit()
    db.refresh(region)
    return region


def get_regions(db: Session, country_id: int, is_active: bool = True):
    return db.query(Region).filter_by(country_id=country_id, is_active=is_active).all()


def get_allowed_regions(db: Session, tenant_id: int, country_id: int, is_active: bool = True):
    return (
        db.query(Region)
        .join(TenantEntity, Region.id == TenantEntity.region_id)
        .filter(
            and_(
                TenantEntity.tenant_id == tenant_id,
                TenantEntity.is_active,
                Region.country_id == country_id,
                Region.is_active == is_active,
            )
        )
        .all()
    )


def get_region(db: Session, pk: int, is_active: bool = True):
    region = db.query(Region).filter_by(id=pk, is_active=is_active).first()
    if not region:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Region not found")
    return region


def delete_region(db: Session, pk: int):
    region = db.query(Region).filter_by(id=pk, is_active=True).first()
    if not region:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Region not found")
    region.is_active = False
    db.commit()
    db.refresh(region)
    return region


def search_region(db: Session, search_name: str):
    search_name_lower = f"%{search_name.lower()}%"
    return db.query(Region).filter(func.lower(Region.name).ilike(search_name_lower)).first()


# -----------------------------Region---------------------------------


# -----------------------------District---------------------------------
def create_district(db: Session, data: DistrictBase):
    exist_district = db.query(District).filter_by(name=data.name, region_id=data.region_id).first()
    if exist_district:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="District already exists")
    region = db.query(Region).filter_by(id=data.region_id, is_active=True).first()
    if not region:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Region not found")
    district = District(name=data.name, region_id=data.region_id)
    db.add(district)
    db.commit()
    db.refresh(district)
    return district


def update_district(db: Session, pk: int, data: DistrictBase):
    exist_district = db.query(District).filter_by(name=data.name, region_id=data.region_id).first()
    if exist_district and exist_district.id != pk:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="District already exists")
    region = db.query(Region).filter_by(id=data.region_id, is_active=True).first()
    if not region:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Region not found")
    district = db.query(District).filter_by(id=pk, is_active=True).first()
    if not district:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="District not found")
    district.name = data.name
    district.region_id = data.region_id
    db.commit()
    db.refresh(district)
    return district


def get_districts(db: Session, region_id: int, is_active: bool = True):
    return db.query(District).filter_by(region_id=region_id, is_active=is_active).all()


def get_allowed_districts(db: Session, tenant_entity_id: int, region_id: int, is_active: bool = True):
    return (
        db.query(District)
        .join(TenantEntity, District.id == TenantEntity.district_id)
        .filter(
            TenantEntity.id == tenant_entity_id,
            TenantEntity.is_active,
            District.region_id == region_id,
            District.is_active == is_active,
        )
        .all()
    )


def get_district(db: Session, pk: int, is_active: bool = True):
    district = db.query(District).filter_by(id=pk, is_active=is_active).first()
    if not district:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="District not found")
    return district


def delete_district(db: Session, pk: int):
    district = db.query(District).filter_by(id=pk, is_active=True).first()
    if not district:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="District not found")
    district.is_active = False
    db.commit()
    db.refresh(district)
    return district


def search_district(db: Session, search_name: str):
    search_name_lower = f"%{search_name.lower()}%"
    return db.query(District).filter(func.lower(District.name).ilike(search_name_lower)).first()


# -----------------------------District---------------------------------
