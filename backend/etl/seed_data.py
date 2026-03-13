"""Generate realistic BSEE-style seed data for development and testing.

Creates incidents, INCs (violations), platforms, and production records
for major Gulf of Mexico operators spanning 2014-2024.

Usage:
    python -m etl.seed_data
"""

import random
import os
import sys

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models.database import Base, DATABASE_PATH
from models.tables import Incident, INC, Platform, Production

# ---------------------------------------------------------------------------
# Reference Data — based on real BSEE data patterns
# ---------------------------------------------------------------------------

OPERATORS = [
    ("WOODSIDE ENERGY", "00001"),
    ("SHELL OFFSHORE INC", "00002"),
    ("BP EXPLORATION & PRODUCTION", "00003"),
    ("CHEVRON USA INC", "00004"),
    ("EXXONMOBIL", "00005"),
    ("MURPHY EXPLORATION & PRODUCTION", "00006"),
    ("W&T OFFSHORE INC", "00007"),
    ("WALTER OIL & GAS CORP", "00008"),
    ("ARENA ENERGY LLC", "00009"),
    ("LLOG EXPLORATION CO LLC", "00010"),
    ("HESS CORPORATION", "00011"),
    ("TALOS ENERGY LLC", "00012"),
    ("ENI US OPERATING CO INC", "00013"),
    ("FIELDWOOD ENERGY LLC", "00014"),
    ("STONE ENERGY CORP", "00015"),
    ("DEEP GULF ENERGY II LLC", "00016"),
    ("RENAISSANCE OFFSHORE LLC", "00017"),
    ("COX OPERATING LLC", "00018"),
    ("ENERGY XXI GIGS LLC", "00019"),
    ("CANTIUM LLC", "00020"),
]

AREAS = [
    "SHIP SHOAL", "SOUTH TIMBALIER", "EUGENE ISLAND", "WEST DELTA",
    "SOUTH PASS", "MAIN PASS", "VERMILION", "EAST CAMERON",
    "WEST CAMERON", "GRAND ISLE", "GREEN CANYON", "MISSISSIPPI CANYON",
    "GARDEN BANKS", "EWING BANK", "VIOSCA KNOLL", "DESOTO CANYON",
    "ATWATER VALLEY", "WALKER RIDGE", "KEATHLEY CANYON", "ALAMINOS CANYON",
]

FACILITY_TYPES = ["Fixed Platform", "SPAR", "TLP", "Semi-submersible", "FPSO",
                   "Caisson", "Well Protector", "Subsea"]

INCIDENT_TYPES = [
    "Fire", "Explosion", "Fatality", "Injury", "Gas Release",
    "Oil Spill", "Collision", "Crane Incident", "Fall", "Struck By",
    "Caught Between", "H2S Release", "Loss of Well Control",
    "Structural Damage", "Equipment Failure", "Electrical",
    "Pressure Release", "Pipeline Leak", "Diving Incident", "Helicopter Incident",
]

CAUSES_OF_LOSS = [
    "Equipment Failure", "Human Error", "Corrosion/Erosion", "Weather",
    "Procedural Violation", "Design Inadequacy", "Maintenance Failure",
    "Material Failure", "Fatigue/Stress Cracking", "Communication Failure",
    "Third Party Damage", "Natural Disaster", "Operator Error",
    "Weld Failure", "Valve Failure", "Pressure Exceedance",
    "Improper Installation", "Inadequate Training",
]

INJURY_TYPES = [
    "No Injury", "First Aid", "Recordable", "Lost Time",
    "Restricted Duty", "Fatality", "Near Miss",
]

INC_COMPONENT_CODES = [
    ("BOP", "Blowout Preventer"),
    ("PSV", "Pressure Safety Valve"),
    ("ESD", "Emergency Shutdown System"),
    ("FGD", "Fire & Gas Detection"),
    ("SSV", "Surface Safety Valve"),
    ("SCSSV", "Subsurface Safety Valve"),
    ("FSV", "Flow Safety Valve"),
    ("LSH", "Level Safety High"),
    ("PSH", "Pressure Safety High"),
    ("PSL", "Pressure Safety Low"),
    ("TSE", "Temperature Safety Element"),
    ("CRANE", "Crane Equipment"),
    ("ELECT", "Electrical Systems"),
    ("STRUCT", "Structural Components"),
    ("PIPE", "Piping Systems"),
    ("PROD", "Production Equipment"),
]

INC_SEVERITIES = ["Warning", "Component Shut-in", "Facility Shut-in"]
INC_SEVERITY_WEIGHTS = [0.55, 0.30, 0.15]  # Most are warnings

DISTRICTS = ["Houma", "Lafayette", "Lake Charles", "New Orleans", "Lake Jackson"]

DESCRIPTIONS_TEMPLATES = [
    "During routine inspection, {cause} was observed on {area} {block}. {detail}",
    "Operator reported {type} on {date}. Investigation found {cause}. {detail}",
    "{type} occurred at {facility} due to {cause}. {detail} No pollution reported.",
    "Worker sustained {injury} while performing {task} operations. {cause} was the contributing factor.",
    "Gas release detected at {facility}. {cause} led to {volume} MCF release. Area evacuated per protocol.",
    "{facility} experienced {type} during {task}. Root cause determined to be {cause}.",
    "During {task} operations, {cause} resulted in {type}. {detail} USCG notified.",
    "Platform {facility} reported {type}. {cause} identified during investigation. {detail}",
]

TASKS = ["drilling", "production", "workover", "completion", "P&A",
         "maintenance", "crane", "diving", "construction", "wireline"]

DETAILS = [
    "Production shut-in for 48 hours pending repairs.",
    "No injuries or environmental impact reported.",
    "Safety systems activated as designed.",
    "Repairs completed and production resumed within 24 hours.",
    "Investigation ongoing. Corrective actions implemented.",
    "Third-party inspection confirmed structural integrity.",
    "Operator submitted corrective action plan within 30 days.",
    "Equipment replaced and tested successfully.",
    "Personnel medically evaluated and released.",
    "Monitoring enhanced in affected area.",
]


def generate_description(incident_type: str, cause: str, area: str, block: str) -> str:
    """Generate a realistic-looking incident description."""
    template = random.choice(DESCRIPTIONS_TEMPLATES)
    return template.format(
        type=incident_type,
        cause=cause,
        area=area,
        block=block,
        facility=f"{area} {block}",
        date=f"{random.randint(1, 12):02d}/{random.randint(1, 28):02d}",
        injury=random.choice(INJURY_TYPES),
        task=random.choice(TASKS),
        volume=random.randint(5, 500),
        detail=random.choice(DETAILS),
    )


def generate_incidents(num_per_operator_year: dict) -> list[dict]:
    """Generate incident records.

    Args:
        num_per_operator_year: dict mapping (operator_idx, year) -> count
    """
    records = []
    incident_id = 100000

    for (op_idx, year), count in num_per_operator_year.items():
        op_name, op_num = OPERATORS[op_idx]
        for _ in range(count):
            incident_id += 1
            area = random.choice(AREAS)
            block = str(random.randint(1, 400))
            incident_type = random.choice(INCIDENT_TYPES)
            cause = random.choice(CAUSES_OF_LOSS)
            inj_type = random.choice(INJURY_TYPES)

            # Determine water depth — deepwater vs shelf
            if area in ["GREEN CANYON", "MISSISSIPPI CANYON", "GARDEN BANKS",
                         "EWING BANK", "WALKER RIDGE", "KEATHLEY CANYON",
                         "ALAMINOS CANYON", "ATWATER VALLEY", "DESOTO CANYON"]:
                water_depth = random.uniform(500, 8000)
            else:
                water_depth = random.uniform(10, 500)

            month = random.randint(1, 12)
            day = random.randint(1, 28)
            date_str = f"{year}-{month:02d}-{day:02d}"

            is_fatal = 1 if (incident_type == "Fatality" or random.random() < 0.005) else 0
            inj_count = random.choices([0, 1, 2, 3], weights=[0.7, 0.2, 0.07, 0.03])[0]
            if is_fatal:
                inj_count = max(inj_count, 1)

            records.append({
                "INCIDENT_ID": incident_id,
                "REPORT_DATE": date_str,
                "INCIDENT_DATE": date_str,
                "OPERATOR_NAME": op_name,
                "OPERATOR_NUM": op_num,
                "LEASE_NUMBER": f"G{random.randint(10000, 99999)}",
                "AREA_NAME": area,
                "BLOCK_NUMBER": block,
                "WATER_DEPTH": round(water_depth, 1),
                "FACILITY_TYPE": random.choice(FACILITY_TYPES),
                "PLATFORM_NAME": f"{area[:3]}-{block}",
                "INJ_TYPE": inj_type,
                "INJ_COUNT": inj_count,
                "FATALITY_COUNT": is_fatal,
                "FIRE_EXPLOSION": "Y" if incident_type in ("Fire", "Explosion") else "N",
                "POLLUTION": "Y" if incident_type in ("Oil Spill", "Gas Release", "Pipeline Leak") else "N",
                "LOSS_WELL_CONTROL": "Y" if incident_type == "Loss of Well Control" else "N",
                "INCIDENT_TYPE": incident_type,
                "CAUSE_OF_LOSS": cause,
                "DESCRIPTION": generate_description(incident_type, cause, area, block),
                "DISTRICT": random.choice(DISTRICTS),
                "YEAR": year,
            })

    return records


def generate_incs(num_per_operator_year: dict) -> list[dict]:
    """Generate INC (violation) records."""
    records = []
    inc_id = 200000

    for (op_idx, year), count in num_per_operator_year.items():
        op_name, op_num = OPERATORS[op_idx]
        for _ in range(count):
            inc_id += 1
            area = random.choice(AREAS)
            block = str(random.randint(1, 400))
            comp_code, comp_desc = random.choice(INC_COMPONENT_CODES)
            severity = random.choices(INC_SEVERITIES, weights=INC_SEVERITY_WEIGHTS)[0]

            if area in ["GREEN CANYON", "MISSISSIPPI CANYON", "GARDEN BANKS",
                         "WALKER RIDGE", "KEATHLEY CANYON"]:
                water_depth = random.uniform(500, 8000)
            else:
                water_depth = random.uniform(10, 500)

            month = random.randint(1, 12)
            day = random.randint(1, 28)

            records.append({
                "INC_ID": inc_id,
                "INC_DATE": f"{year}-{month:02d}-{day:02d}",
                "OPERATOR_NAME": op_name,
                "OPERATOR_NUM": op_num,
                "LEASE_NUMBER": f"G{random.randint(10000, 99999)}",
                "AREA_NAME": area,
                "BLOCK_NUMBER": block,
                "WATER_DEPTH": round(water_depth, 1),
                "PLATFORM_NAME": f"{area[:3]}-{block}",
                "COMPONENT_CODE": comp_code,
                "COMPONENT_DESC": comp_desc,
                "SEVERITY": severity,
                "INC_TYPE": f"30 CFR 250.{random.randint(800, 899)}",
                "SUBPART": random.choice(["H", "I", "J", "K", "L", "M", "N"]),
                "SECTION": str(random.randint(800, 899)),
                "DESCRIPTION": f"{severity} issued for {comp_desc} ({comp_code}) — "
                               f"found non-compliant during inspection.",
                "DISTRICT": random.choice(DISTRICTS),
                "YEAR": year,
            })

    return records


def generate_platforms() -> list[dict]:
    """Generate platform records for each operator."""
    records = []
    platform_id = 300000

    for op_idx, (op_name, op_num) in enumerate(OPERATORS):
        # Larger operators have more platforms
        if op_idx < 5:
            num_platforms = random.randint(40, 80)
        elif op_idx < 10:
            num_platforms = random.randint(15, 40)
        else:
            num_platforms = random.randint(5, 20)

        for _ in range(num_platforms):
            platform_id += 1
            area = random.choice(AREAS)
            block = str(random.randint(1, 400))

            if area in ["GREEN CANYON", "MISSISSIPPI CANYON", "GARDEN BANKS",
                         "WALKER RIDGE", "KEATHLEY CANYON"]:
                water_depth = random.uniform(500, 8000)
                ftype = random.choice(["SPAR", "TLP", "Semi-submersible", "FPSO", "Subsea"])
            else:
                water_depth = random.uniform(10, 500)
                ftype = random.choice(["Fixed Platform", "Caisson", "Well Protector"])

            install_year = random.randint(1970, 2020)
            removed = random.random() < 0.15
            status = "Removed" if removed else "Active"

            records.append({
                "PLATFORM_ID": platform_id,
                "PLATFORM_NAME": f"{area[:3]}-{block}-{platform_id % 1000}",
                "OPERATOR_NAME": op_name,
                "OPERATOR_NUM": op_num,
                "AREA_NAME": area,
                "BLOCK_NUMBER": block,
                "WATER_DEPTH": round(water_depth, 1),
                "INSTALL_DATE": f"{install_year}-01-01",
                "REMOVAL_DATE": f"{install_year + random.randint(15, 40)}-01-01" if removed else None,
                "FACILITY_TYPE": ftype,
                "STATUS": status,
                "DISTRICT": random.choice(DISTRICTS),
                "LATITUDE": round(random.uniform(26.5, 29.5), 4),
                "LONGITUDE": round(random.uniform(-93.0, -87.0), 4),
            })

    return records


def generate_production() -> list[dict]:
    """Generate monthly production records per operator (2014-2024)."""
    records = []

    # Base annual production by operator tier (in barrels/MCF per month)
    for op_idx, (op_name, op_num) in enumerate(OPERATORS):
        if op_idx < 5:  # Major operators
            base_oil = random.uniform(800_000, 3_000_000)
            base_gas = random.uniform(2_000_000, 8_000_000)
        elif op_idx < 10:  # Mid-tier
            base_oil = random.uniform(200_000, 800_000)
            base_gas = random.uniform(500_000, 2_000_000)
        else:  # Smaller operators
            base_oil = random.uniform(20_000, 200_000)
            base_gas = random.uniform(50_000, 500_000)

        for year in range(2014, 2025):
            # Add year-over-year variation (production decline + new wells)
            year_factor = 1.0 + random.uniform(-0.15, 0.10) * ((year - 2014) / 10)
            for month in range(1, 13):
                # Monthly seasonality
                month_factor = 1.0 + 0.05 * random.uniform(-1, 1)
                oil = max(0, base_oil * year_factor * month_factor * random.uniform(0.85, 1.15))
                gas = max(0, base_gas * year_factor * month_factor * random.uniform(0.85, 1.15))

                records.append({
                    "OPERATOR_NAME": op_name,
                    "OPERATOR_NUM": op_num,
                    "LEASE_NUMBER": f"G{random.randint(10000, 99999)}",
                    "AREA_NAME": random.choice(AREAS),
                    "BLOCK_NUMBER": str(random.randint(1, 400)),
                    "YEAR": year,
                    "MONTH": month,
                    "OIL_BBL": round(oil, 0),
                    "GAS_MCF": round(gas, 0),
                    "WATER_BBL": round(oil * random.uniform(0.3, 1.5), 0),
                    "DAYS_ON": random.randint(25, 31),
                })

    return records


def seed_database():
    """Create all tables and populate with seed data."""
    random.seed(42)  # Reproducible data

    db_path = os.getenv("DATABASE_PATH", "./data/bsee.db")
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Remove existing DB for clean seed
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Removed existing database: {db_path}")

    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    print("=" * 60)
    print("BSEE Seed Data Generator")
    print("=" * 60)

    # --- Generate incident counts per operator per year ---
    # More incidents for larger operators, with slight improvement trend over years
    incident_counts = {}
    inc_counts = {}
    for op_idx in range(len(OPERATORS)):
        for year in range(2014, 2025):
            if op_idx < 5:
                base_incidents = random.randint(15, 40)
                base_incs = random.randint(30, 80)
            elif op_idx < 10:
                base_incidents = random.randint(5, 20)
                base_incs = random.randint(10, 40)
            else:
                base_incidents = random.randint(1, 10)
                base_incs = random.randint(3, 20)

            # Slight improvement trend (fewer incidents over time)
            trend = max(0.5, 1.0 - (year - 2014) * 0.02)
            incident_counts[(op_idx, year)] = max(1, int(base_incidents * trend))
            inc_counts[(op_idx, year)] = max(1, int(base_incs * trend))

    # 1. Incidents
    print("Generating incidents...")
    incidents = generate_incidents(incident_counts)
    for rec in incidents:
        session.add(Incident(**rec))
    session.flush()
    print(f"  {len(incidents)} incident records created")

    # 2. INCs (Violations)
    print("Generating INCs (violations)...")
    incs = generate_incs(inc_counts)
    for rec in incs:
        session.add(INC(**rec))
    session.flush()
    print(f"  {len(incs)} INC records created")

    # 3. Platforms
    print("Generating platforms...")
    platforms = generate_platforms()
    for rec in platforms:
        session.add(Platform(**rec))
    session.flush()
    print(f"  {len(platforms)} platform records created")

    # 4. Production
    print("Generating production data...")
    production = generate_production()
    for rec in production:
        session.add(Production(**rec))
    session.flush()
    print(f"  {len(production)} production records created")

    session.commit()
    session.close()

    print("=" * 60)
    print(f"Database seeded: {db_path}")
    total = len(incidents) + len(incs) + len(platforms) + len(production)
    print(f"Total records: {total:,}")
    print("=" * 60)


if __name__ == "__main__":
    seed_database()
