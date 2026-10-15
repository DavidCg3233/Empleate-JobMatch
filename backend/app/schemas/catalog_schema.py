from pydantic import BaseModel


class CityOut(BaseModel):
    id: int
    name: str
    department: str


class IndustryOut(BaseModel):
    id: int
    name: str

class CatalogItemOut(BaseModel):
    id: int
    name: str
