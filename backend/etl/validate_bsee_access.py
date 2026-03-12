"""Validate connectivity to BSEE public data sources.

Run this script to confirm that BSEE data endpoints are reachable
before attempting full data downloads.
"""

import httpx
import sys


BSEE_DATA_SOURCES = {
    "Incidents": "https://www.data.bsee.gov/Incident/Files/IncidentData.zip",
    "INCs (Violations)": "https://www.data.bsee.gov/INCs/Files/INCData.zip",
    "Platforms": "https://www.data.bsee.gov/Platform/Files/PlatformData.zip",
    "Production": "https://www.data.bsee.gov/Production/Files/ProductionData.zip",
    "Wells": "https://www.data.bsee.gov/Well/Files/WellData.zip",
    "Safety Alerts": "https://www.bsee.gov/",
}


def validate_access() -> bool:
    """Check connectivity to each BSEE data source via HEAD request."""
    all_passed = True
    print("=" * 60)
    print("BSEE Data Source Connectivity Check")
    print("=" * 60)

    for name, url in BSEE_DATA_SOURCES.items():
        try:
            response = httpx.head(url, follow_redirects=True, timeout=15.0)
            if response.status_code < 400:
                print(f"  PASS  {name} ({response.status_code})")
            else:
                print(f"  FAIL  {name} ({response.status_code})")
                all_passed = False
        except httpx.RequestError as e:
            print(f"  FAIL  {name} (Error: {e})")
            all_passed = False

    print("=" * 60)
    if all_passed:
        print("All data sources reachable.")
    else:
        print("Some data sources are unreachable. Check network connectivity.")
    print("=" * 60)
    return all_passed


if __name__ == "__main__":
    success = validate_access()
    sys.exit(0 if success else 1)
