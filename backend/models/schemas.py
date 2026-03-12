from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    data: T
    meta: dict | None = None


class APIError(BaseModel):
    error: str
    detail: str | None = None
    status: int


class Operator(BaseModel):
    id: str
    name: str
    incident_count: int = 0
    inc_count: int = 0


class Incident(BaseModel):
    id: str
    date: str
    operator: str
    description: str = ""
    severity: str = ""


class INC(BaseModel):
    id: str
    date: str
    operator: str
    inc_type: str = ""
    status: str = ""


class Platform(BaseModel):
    id: str
    name: str
    operator: str
    area: str = ""
    block: str = ""
    inc_count: int = 0


class Production(BaseModel):
    operator: str
    year: int
    month: int
    oil_bbl: float = 0.0
    gas_mcf: float = 0.0
    boe: float = 0.0
