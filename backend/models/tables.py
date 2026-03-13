"""SQLAlchemy ORM models for BSEE data tables.

Column names follow BSEE data dictionary conventions (ALL_CAPS with underscores).
Tables: incidents, incs (violations), platforms, production, incident_root_causes.
"""

from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, ForeignKey, Index, JSON
)
from sqlalchemy.orm import relationship
from models.database import Base


class Incident(Base):
    """BSEE incident records — injuries, fatalities, fires, explosions, spills."""
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    INCIDENT_ID = Column(Integer, unique=True, nullable=False, index=True)
    REPORT_DATE = Column(String(20))
    INCIDENT_DATE = Column(String(20), index=True)
    OPERATOR_NAME = Column(String(200), index=True)
    OPERATOR_NUM = Column(String(20))
    LEASE_NUMBER = Column(String(20))
    AREA_NAME = Column(String(100))
    BLOCK_NUMBER = Column(String(20))
    WATER_DEPTH = Column(Float)
    FACILITY_TYPE = Column(String(50))
    PLATFORM_NAME = Column(String(100))
    INJ_TYPE = Column(String(100))  # Injury type
    INJ_COUNT = Column(Integer, default=0)
    FATALITY_COUNT = Column(Integer, default=0)
    FIRE_EXPLOSION = Column(String(10))  # Y/N
    POLLUTION = Column(String(10))  # Y/N
    LOSS_WELL_CONTROL = Column(String(10))  # Y/N
    INCIDENT_TYPE = Column(String(200))
    CAUSE_OF_LOSS = Column(String(200))
    DESCRIPTION = Column(Text)
    DISTRICT = Column(String(50))
    YEAR = Column(Integer, index=True)

    # Relationship to AI root cause categorizations
    root_causes = relationship("IncidentRootCause", back_populates="incident")

    __table_args__ = (
        Index("ix_incidents_operator_year", "OPERATOR_NAME", "YEAR"),
    )


class INC(Base):
    """BSEE Incidents of Non-Compliance (violations / INCs)."""
    __tablename__ = "incs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    INC_ID = Column(Integer, unique=True, nullable=False, index=True)
    INC_DATE = Column(String(20), index=True)
    OPERATOR_NAME = Column(String(200), index=True)
    OPERATOR_NUM = Column(String(20))
    LEASE_NUMBER = Column(String(20))
    AREA_NAME = Column(String(100))
    BLOCK_NUMBER = Column(String(20))
    WATER_DEPTH = Column(Float)
    PLATFORM_NAME = Column(String(100))
    COMPONENT_CODE = Column(String(100))
    COMPONENT_DESC = Column(String(200))
    SEVERITY = Column(String(50))  # Warning, Component Shut-in, Facility Shut-in
    INC_TYPE = Column(String(200))
    SUBPART = Column(String(50))
    SECTION = Column(String(50))
    DESCRIPTION = Column(Text)
    DISTRICT = Column(String(50))
    YEAR = Column(Integer, index=True)

    __table_args__ = (
        Index("ix_incs_operator_year", "OPERATOR_NAME", "YEAR"),
        Index("ix_incs_severity", "SEVERITY", "YEAR"),
    )


class Platform(Base):
    """BSEE platform/facility records."""
    __tablename__ = "platforms"

    id = Column(Integer, primary_key=True, autoincrement=True)
    PLATFORM_ID = Column(Integer, unique=True, nullable=False, index=True)
    PLATFORM_NAME = Column(String(100))
    OPERATOR_NAME = Column(String(200), index=True)
    OPERATOR_NUM = Column(String(20))
    AREA_NAME = Column(String(100))
    BLOCK_NUMBER = Column(String(20))
    WATER_DEPTH = Column(Float)
    INSTALL_DATE = Column(String(20))
    REMOVAL_DATE = Column(String(20))
    FACILITY_TYPE = Column(String(50))  # Fixed, SPAR, TLP, Semi, FPSO, etc.
    STATUS = Column(String(50))  # Active, Removed, etc.
    DISTRICT = Column(String(50))
    LATITUDE = Column(Float)
    LONGITUDE = Column(Float)


class Production(Base):
    """BSEE production volumes — monthly oil and gas by operator/lease."""
    __tablename__ = "production"

    id = Column(Integer, primary_key=True, autoincrement=True)
    OPERATOR_NAME = Column(String(200), index=True)
    OPERATOR_NUM = Column(String(20))
    LEASE_NUMBER = Column(String(20))
    AREA_NAME = Column(String(100))
    BLOCK_NUMBER = Column(String(20))
    YEAR = Column(Integer, index=True)
    MONTH = Column(Integer)
    OIL_BBL = Column(Float, default=0.0)  # Oil production in barrels
    GAS_MCF = Column(Float, default=0.0)  # Gas production in MCF
    WATER_BBL = Column(Float, default=0.0)  # Water production in barrels
    DAYS_ON = Column(Integer, default=0)  # Days the well/lease was producing

    __table_args__ = (
        Index("ix_production_operator_year", "OPERATOR_NAME", "YEAR"),
    )


class IncidentRootCause(Base):
    """AI-generated root cause categorizations for incidents (Step 2.5)."""
    __tablename__ = "incident_root_causes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incident_id = Column(Integer, ForeignKey("incidents.INCIDENT_ID"), unique=True, index=True)
    primary_cause = Column(String(50), nullable=False, index=True)
    root_causes = Column(JSON)  # JSON array of cause strings
    confidence = Column(Float)
    reasoning = Column(Text)
    categorized_at = Column(String(30))  # ISO timestamp

    incident = relationship("Incident", back_populates="root_causes")
