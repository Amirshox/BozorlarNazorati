from typing import List

from pydantic import BaseModel


class CountryBase(BaseModel):
    name: str


class RegionBase(BaseModel):
    name: str
    country_id: int


class DistrictBase(BaseModel):
    name: str
    region_id: int
    country_id: int


class DistrictSchema(BaseModel):
    id: int
    name: str
    region_id: int
    country_id: int

    class Config:
        from_attributes = True


class RegionSchema(BaseModel):
    id: int
    name: str
    country_id: int

    class Config:
        from_attributes = True


class CountrySchema(BaseModel):
    id: int
    name: str


class DistrictInDB(DistrictSchema):
    id: int
    country: CountrySchema
    region: RegionSchema


class RegionInDB(RegionSchema):
    id: int
    country: CountrySchema
    districts: List[DistrictSchema]


class CountryInDB(CountryBase):
    id: int
    regions: List[RegionSchema]
