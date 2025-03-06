from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi_pagination.ext.sqlalchemy import paginate
from sqlalchemy import and_, func
from sqlalchemy.orm import Session
from starlette import status

from auth.oauth2 import get_tenant_entity_user
from database import db_tenant_entity, db_wanted
from database.database import get_pg_db
from models import Identity, TenantEntity
from schemas.tenant_hierarchy_entity import EntityForFilter, EntityGroup, TenantEntityInDB
from schemas.wanted import WantedInDB
from utils.pagination import CustomPage
from utils.redis_cache import get_from_redis, get_redis_connection, serialize_tenant_entity, set_to_redis

router = APIRouter(prefix="/tenant_entity_customer", tags=["tenant_entity_customer"])


@router.get("/")
def get_customer_tenant_entities(
    tenant_entity_id: Optional[int] = None,
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user),
    redis_client=Depends(get_redis_connection),
):
    me = db_tenant_entity.get_tenant_entity(db, user.tenant_id, user.tenant_entity_id)
    if tenant_entity_id:
        parent = db.query(TenantEntity).filter_by(id=tenant_entity_id, tenant_id=user.tenant_id, is_active=True).first()
        if not parent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant entity not found")
        if parent.hierarchy_level <= me.hierarchy_level:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="You have no permission to access this tenant entity"
            )
        cache_key = f"entity:{tenant_entity_id}:children"
        cached_data = get_from_redis(redis_client, cache_key)
        if cached_data:
            return cached_data
        children = db_tenant_entity.get_tenant_entity_children(db, user.tenant_id, tenant_entity_id).all()
        data = {
            "relative": serialize_tenant_entity(parent),
            "children": [serialize_tenant_entity(child) for child in children],
        }
        set_to_redis(redis_client, cache_key, data)
        return data
    cache_key = f"entity:{user.tenant_entity_id}:children"
    cached_data = get_from_redis(redis_client, cache_key)
    if cached_data:
        return cached_data
    children = db_tenant_entity.get_tenant_entity_children(db, user.tenant_id, user.tenant_entity_id).all()
    data = {"relative": serialize_tenant_entity(me), "children": [serialize_tenant_entity(child) for child in children]}
    set_to_redis(redis_client, cache_key, data)
    return data


@router.get("/for_filter", response_model=List[EntityForFilter])
def get_customer_tenant_entities_for_filter(
    search: Optional[str] = Query(None, alias="search"),
    db: Session = Depends(get_pg_db),
    user=Security(get_tenant_entity_user),
    redis_client=Depends(get_redis_connection),
):
    cache_key = f"entity:{user.tenant_entity_id}:filter"
    if not search:
        cached_data = get_from_redis(redis_client, cache_key)
        if cached_data:
            return cached_data
    me = db_tenant_entity.get_tenant_entity(db, user.tenant_id, user.tenant_entity_id)
    me = [EntityForFilter.from_orm(me).dict()]
    children = db_tenant_entity.get_tenant_entity_children(db, user.tenant_id, user.tenant_entity_id, search).all()
    children = [EntityForFilter.from_orm(identity).dict() for identity in children]
    result = me + children
    if not search:
        set_to_redis(redis_client, cache_key, result)
    return result


@router.get("/wanteds", response_model=CustomPage[WantedInDB])
def get_wanteds(db: Session = Depends(get_pg_db), user=Security(get_tenant_entity_user)):
    return paginate(db_wanted.get_wanteds(db))


@router.get("/wanteds/all", response_model=List[WantedInDB])
def get_wanteds_without_pagination(db: Session = Depends(get_pg_db), user=Security(get_tenant_entity_user)):
    return db_wanted.get_wanteds(db).all()


@router.get("/info", response_model=TenantEntityInDB)
def get_tenant_entities_mobile_info(db: Session = Depends(get_pg_db), user=Security(get_tenant_entity_user)):
    tenant_entity = db_tenant_entity.get_tenant_entity_info(db, user.tenant_id, user.tenant_entity_id)
    groups_query = (
        db.query(
            Identity.group_id,
            func.max(Identity.group_name).label("group_name"),
            func.max(Identity.lat).label("lat").label("lat"),
            func.max(Identity.lon).label("lon").label("lon"),
        )
        .where(and_(Identity.tenant_entity_id == tenant_entity.id, Identity.identity_group == 0, Identity.is_active))
        .group_by(Identity.group_id)
    )
    result = TenantEntityInDB(**tenant_entity.__dict__)
    groups = [
        EntityGroup(group_id=i.group_id, group_name=i.group_name, lat=i.lat, lon=i.lon) for i in groups_query.all()
    ]
    result.groups = groups
    return result
