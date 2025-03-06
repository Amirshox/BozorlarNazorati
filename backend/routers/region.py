from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Security
from sqlalchemy.orm import Session

from auth.oauth2 import is_authenticated
from database import db_region
from database.database import get_pg_db
from schemas.region import (
    CountryBase,
    CountryInDB,
    CountrySchema,
    DistrictBase,
    DistrictInDB,
    DistrictSchema,
    RegionBase,
    RegionInDB,
    RegionSchema,
)
from utils.redis_cache import get_from_redis, get_redis_connection, set_to_redis

router = APIRouter(prefix="/region", tags=["region"])


@router.post("/country", response_model=CountrySchema)
def create_country(data: CountryBase, db: Session = Depends(get_pg_db), authenticated=Security(is_authenticated)):
    return db_region.create_country(db, data)


@router.put("/country/{pk}", response_model=CountryInDB)
def update_country(
    pk: int, data: CountryBase, db: Session = Depends(get_pg_db), authenticated=Security(is_authenticated)
):
    return db_region.update_country(db, pk, data)


@router.get("/country", response_model=List[CountrySchema])
def get_countries(
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    redis_client=Depends(get_redis_connection),
    authenticated=Security(is_authenticated),
):
    cached_countries = get_from_redis(redis_client, "countries")
    if cached_countries:
        return cached_countries
    countries = db_region.get_countries(db, is_active)
    serialized_countries = [country.to_dict() for country in countries]
    set_to_redis(redis_client, "countries", serialized_countries)
    return serialized_countries


@router.get("/country/{pk}", response_model=CountryInDB)
def get_country(
    pk: int,
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    authenticated=Security(is_authenticated),
):
    return db_region.get_country(db, pk, is_active)


@router.delete("/country/{pk}", response_model=CountryInDB)
def delete_country(pk: int, db: Session = Depends(get_pg_db), authenticated=Security(is_authenticated)):
    return db_region.delete_country(db, pk)


@router.post("/district", response_model=DistrictSchema)
def create_district(data: DistrictBase, db: Session = Depends(get_pg_db), authenticated=Security(is_authenticated)):
    return db_region.create_district(db, data)


@router.put("/district/{pk}", response_model=DistrictInDB)
def update_district(
    pk: int, data: DistrictBase, db: Session = Depends(get_pg_db), authenticated=Security(is_authenticated)
):
    return db_region.update_district(db, pk, data)


@router.get("/district", response_model=List[DistrictSchema])
async def get_districts(
    region_id: int,
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    redis_client=Depends(get_redis_connection),
    authenticated=Security(is_authenticated),
):
    cached_districts = get_from_redis(redis_client, f"{region_id}:districts")
    if cached_districts:
        return cached_districts
    districts = db_region.get_districts(db, region_id, is_active)
    serialized_districts = [district.to_dict() for district in districts]
    set_to_redis(redis_client, f"{region_id}:districts", serialized_districts)
    return serialized_districts


# @router.get("/allowed-districts", response_model=List[DistrictSchema])
# async def get_allowed_districts(
#     tenant_id: int,
#     region_id: int,
#     db: Session = Depends(get_pg_db),
#     redis_client=Depends(get_redis_connection),
#     authenticated=Security(is_authenticated),
# ):
#     districts = db_region.get_allowed_districts(db, tenant_id, region_id)
#     serialized_districts = [district.to_dict() for district in districts]
#     return serialized_districts


@router.get("/district/{pk}", response_model=DistrictInDB)
def get_district(
    pk: int,
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    authenticated=Security(is_authenticated),
):
    return db_region.get_district(db, pk, is_active)


@router.delete("/district/{pk}", response_model=DistrictInDB)
def delete_district(pk: int, db: Session = Depends(get_pg_db), authenticated=Security(is_authenticated)):
    return db_region.delete_district(db, pk)


@router.post("/", response_model=RegionSchema)
def create_region(data: RegionBase, db: Session = Depends(get_pg_db), authenticated=Security(is_authenticated)):
    return db_region.create_region(db, data)


@router.put("/{pk}", response_model=RegionInDB)
def update_region(
    pk: int, data: RegionBase, db: Session = Depends(get_pg_db), authenticated=Security(is_authenticated)
):
    return db_region.update_region(db, pk, data)


@router.get("/", response_model=List[RegionSchema])
async def get_regions(
    country_id: int,
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    redis_client=Depends(get_redis_connection),
    authenticated=Security(is_authenticated),
):
    cached_regions = get_from_redis(redis_client, f"{country_id}:regions")
    if cached_regions:
        return cached_regions
    regions = db_region.get_regions(db, country_id, is_active)
    serialized_regions = [region.to_dict() for region in regions]
    set_to_redis(redis_client, f"{country_id}:regions", serialized_regions)
    return serialized_regions


@router.get("/allowed-regions", response_model=List[RegionSchema])
async def get_allowed_regions(
    country_id: int,
    db: Session = Depends(get_pg_db),
    redis_client=Depends(get_redis_connection),
    authenticated=Security(is_authenticated),
):
    regions = db_region.get_regions(db, country_id)
    serialized_regions = [region.to_dict() for region in regions]
    return serialized_regions


@router.get("/{pk}", response_model=RegionInDB)
def get_region(
    pk: int,
    is_active: Optional[bool] = Query(default=True, alias="is_active"),
    db: Session = Depends(get_pg_db),
    authenticated=Security(is_authenticated),
):
    return db_region.get_region(db, pk, is_active)


@router.delete("/{pk}", response_model=RegionInDB)
def delete_region(pk: int, db: Session = Depends(get_pg_db), authenticated=Security(is_authenticated)):
    return db_region.delete_region(db, pk)
