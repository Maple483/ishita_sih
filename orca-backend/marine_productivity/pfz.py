"""PFZ advisory service used by the Marine Productivity UI.

This module ports only the working PFZ-ranking portion of the ORCA
marine-productivity service into the modular backend used by ishita_sih.
It does not alter the historical fisheries-analysis endpoints.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from csv import DictReader
from datetime import datetime, timedelta, timezone
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import requests
from fastapi import APIRouter, Query


router = APIRouter()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PFZ_FILE = DATA_DIR / "pfz_advisories.csv"
ENVIRONMENT_FILE = DATA_DIR / "synthetic_indian_coastal_sst_chlorophyll_2007_2012.csv"

OPEN_METEO_MARINE = "https://marine-api.open-meteo.com/v1/marine"
NOAA_MUR_ERDDAP = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41.json"
NOAA_CHL_GAPFILLED_ERDDAP = (
    "https://coastwatch.pfeg.noaa.gov/erddap/griddap/"
    "nesdisVHNnoaaSNPPnoaa20chlaGapfilledDaily.json"
)
NOAA_CHL_NRT_ERDDAP = (
    "https://coastwatch.pfeg.noaa.gov/erddap/griddap/"
    "nesdisVHNnoaa20chlaDaily_Lon0360.json"
)


def _to_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(d_lon / 2) ** 2
    )
    return 2 * radius_km * math.asin(min(1.0, math.sqrt(a)))


def _load_pfz_records() -> List[Dict[str, Any]]:
    if not PFZ_FILE.exists():
        return []

    records: List[Dict[str, Any]] = []
    with PFZ_FILE.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = DictReader(handle)
        for row in reader:
            lat = _to_float(row.get("Latitude_Decimal"))
            lon = _to_float(row.get("Longitude_Decimal"))
            if lat is None or lon is None:
                continue
            row["Latitude_Decimal"] = lat
            row["Longitude_Decimal"] = lon
            row["Bearing (deg)"] = _to_float(row.get("Bearing (deg)"))
            row["State"] = _clean(row.get("State"))
            records.append(row)
    return records


def _marine(lat: float, lon: float) -> Dict[str, Any]:
    """Get live model marine conditions, matching the working ORCA service."""
    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": (
                "sea_surface_temperature,wave_height,wave_direction,wave_period,"
                "ocean_current_velocity,ocean_current_direction"
            ),
            "timezone": "GMT",
            "cell_selection": "sea",
        }
        response = requests.get(OPEN_METEO_MARINE, params=params, timeout=8)
        response.raise_for_status()
        current = response.json().get("current", {})
        return {
            "sst_c": current.get("sea_surface_temperature"),
            "wave_height_m": current.get("wave_height"),
            "wave_direction_deg": current.get("wave_direction"),
            "wave_period_s": current.get("wave_period"),
            "current_velocity_kmh": current.get("ocean_current_velocity"),
            "current_direction_deg": current.get("ocean_current_direction"),
            "source": "Open-Meteo Marine",
        }
    except Exception as exc:
        return {
            "sst_c": None,
            "wave_height_m": None,
            "wave_direction_deg": None,
            "wave_period_s": None,
            "current_velocity_kmh": None,
            "current_direction_deg": None,
            "source": "Live marine feed unavailable",
            "error": str(exc),
        }


def _satellite_sst(lat: float, lon: float) -> Optional[float]:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
    try:
        query = f"analysed_sst[({date})][({lat})][({lon})]"
        response = requests.get(
            NOAA_MUR_ERDDAP,
            params={"query": query},
            timeout=8,
        )
        response.raise_for_status()
        rows = response.json().get("table", {}).get("rows", [])
        value = rows[0][-1] if rows else None
        number = _to_float(value)
        return number if number is not None and number > -100 else None
    except Exception:
        return None


def _satellite_chlorophyll(lat: float, lon: float) -> Optional[float]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=14)
    start_s = start.strftime("%Y-%m-%dT00:00:00Z")
    end_s = end.strftime("%Y-%m-%dT23:59:59Z")

    for endpoint in (NOAA_CHL_GAPFILLED_ERDDAP, NOAA_CHL_NRT_ERDDAP):
        try:
            query = f"chlor_a[({start_s}):1:({end_s})][({lat})][({lon})]"
            response = requests.get(
                endpoint,
                params={"query": query},
                timeout=10,
            )
            response.raise_for_status()
            rows = response.json().get("table", {}).get("rows", [])
            values: List[float] = []
            for row in rows:
                value = _to_float(row[-1] if row else None)
                if value is not None and value > 0:
                    values.append(value)
            if values:
                return values[-1]
        except Exception:
            continue
    return None


def _freshness(text: Any, now: datetime) -> float:
    match = re.search(
        r"FROM\s+(\d{1,2}\s+\w+\s+\d{4})\s+TO\s+(\d{1,2}\s+\w+\s+\d{4})",
        str(text or ""),
        re.IGNORECASE,
    )
    if not match:
        return 0.5

    try:
        start = datetime.strptime(match.group(1), "%d %b %Y").replace(tzinfo=timezone.utc)
        end = datetime.strptime(match.group(2), "%d %b %Y").replace(tzinfo=timezone.utc)
    except ValueError:
        return 0.5

    if start <= now <= end:
        return 1.0
    if now > end:
        return max(0.0, 1.0 - (now - end).total_seconds() / (14 * 86400))
    return 0.8


def _state_key(state: Any) -> str:
    normalized = _clean(state).lower()
    aliases = {
        "north andhra pradesh": "andhra pradesh",
        "south andhra pradesh": "andhra pradesh",
        "north tamil nadu": "tamil nadu",
        "south tamil nadu": "tamil nadu",
        "pondicherry": "puducherry",
        "pondy": "puducherry",
        "a & n islands": "andaman & nicobar",
    }
    return aliases.get(normalized, normalized)


def _sst_suitability(sst: Any) -> Optional[float]:
    value = _to_float(sst)
    if value is None:
        return None
    # Same broad suitability curve used by the working ORCA PFZ service.
    return round(max(0.0, min(100.0, 100.0 - abs(value - 27.0) / 6.0 * 100.0)), 1)


def _scale_score(value: Any, low: Optional[float], high: Optional[float]) -> Optional[float]:
    number = _to_float(value)
    if number is None or low is None or high is None or high <= low:
        return None
    return round(max(0.0, min(100.0, (number - low) / (high - low) * 100.0)), 1)


def _historical_profiles() -> tuple[Dict[str, Dict[str, float]], Optional[float], Optional[float]]:
    """Build lightweight state climatologies without adding a pandas dependency."""
    if not ENVIRONMENT_FILE.exists():
        return {}, None, None

    by_state: Dict[str, Dict[str, List[float]]] = {}
    all_chlorophyll: List[float] = []

    with ENVIRONMENT_FILE.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = DictReader(handle)
        for row in reader:
            state = _state_key(row.get("State"))
            sst = _to_float(row.get("SST_C"))
            chl = _to_float(row.get("Chlorophyll_mg_m3"))
            if not state or sst is None or chl is None or chl <= 0:
                continue
            bucket = by_state.setdefault(state, {"sst": [], "chl": []})
            bucket["sst"].append(sst)
            bucket["chl"].append(chl)
            all_chlorophyll.append(chl)

    if not all_chlorophyll:
        return {}, None, None

    chl_low = float(np.quantile(all_chlorophyll, 0.10))
    chl_high = float(np.quantile(all_chlorophyll, 0.90))
    profiles: Dict[str, Dict[str, float]] = {}

    for state, values in by_state.items():
        sst_values = values["sst"]
        chl_values = values["chl"]
        sst_scores = [
            score for score in (_sst_suitability(value) for value in sst_values)
            if score is not None
        ]
        profiles[state] = {
            "sst_mean_c": float(np.mean(sst_values)),
            "chlorophyll_mean_mg_m3": float(np.mean(chl_values)),
            "sst_score": float(np.mean(sst_scores)) if sst_scores else 0.0,
            "chlorophyll_score": float(
                _scale_score(float(np.mean(chl_values)), chl_low, chl_high) or 0.0
            ),
        }

    return profiles, chl_low, chl_high


def _candidate_live(record: Dict[str, Any]) -> Dict[str, Any]:
    lat = float(record["Latitude_Decimal"])
    lon = float(record["Longitude_Decimal"])
    satellite_sst = _satellite_sst(lat, lon)
    chlorophyll = _satellite_chlorophyll(lat, lon)
    sst_source = (
        "NASA/JPL MUR satellite SST via NOAA ERDDAP"
        if satellite_sst is not None
        else ""
    )

    if satellite_sst is None:
        fallback = _marine(lat, lon)
        satellite_sst = _to_float(fallback.get("sst_c"))
        if satellite_sst is not None:
            sst_source = str(fallback.get("source", ""))

    return {
        "sst_c": satellite_sst,
        "chlorophyll_mg_m3": chlorophyll,
        "sst_source": sst_source,
        "chlorophyll_source": (
            "NOAA VIIRS chlorophyll via CoastWatch ERDDAP"
            if chlorophyll is not None
            else ""
        ),
    }


@router.get("/pfz")
def find_pfz(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    max_results: int = Query(5, ge=1, le=10),
):
    """Return ranked PFZ advisories for a fisherman location.

    Ranking mirrors the previously working sih_orca service while using the
    existing ishita_sih PFZ advisory and historical-environment data files.
    """
    advisories = _load_pfz_records()
    now = datetime.now(timezone.utc)
    marine = _marine(lat, lon)

    satellite_sst = _satellite_sst(lat, lon)
    if satellite_sst is not None:
        marine["satellite_sst_c"] = satellite_sst
        marine["satellite_sst_source"] = "NASA/JPL MUR satellite SST via NOAA ERDDAP"

    if not advisories:
        return {
            "status": "NO_ADVISORIES",
            "user_location": {"lat": lat, "lon": lon},
            "live_conditions": marine,
            "results": [],
            "message": "No PFZ advisory records are available.",
        }

    profiles, chl_low, chl_high = _historical_profiles()

    live_by_index: Dict[int, Dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(8, len(advisories))) as executor:
        futures = {
            executor.submit(_candidate_live, record): index
            for index, record in enumerate(advisories)
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                live_by_index[index] = future.result()
            except Exception:
                live_by_index[index] = {
                    "sst_c": None,
                    "chlorophyll_mg_m3": None,
                    "sst_source": "",
                    "chlorophyll_source": "",
                }

    ranked: List[Dict[str, Any]] = []

    for index, record in enumerate(advisories):
        pfz_lat = float(record["Latitude_Decimal"])
        pfz_lon = float(record["Longitude_Decimal"])
        distance = _haversine(lat, lon, pfz_lat, pfz_lon)
        fresh = _freshness(record.get("Forecast_Validity"), now)
        live = live_by_index.get(index, {})
        live_sst = _to_float(live.get("sst_c"))
        live_chl = _to_float(live.get("chlorophyll_mg_m3"))
        history = profiles.get(_state_key(record.get("State")))

        components: List[tuple[float, float]] = []
        details: Dict[str, float] = {}

        proximity_score = max(0.0, min(100.0, 100.0 * math.exp(-distance / 250.0)))
        components.append((0.20, proximity_score))
        details["proximity"] = round(proximity_score, 1)

        freshness_score = max(0.0, min(100.0, fresh * 100.0))
        components.append((0.10, freshness_score))
        details["advisory_freshness"] = round(freshness_score, 1)

        live_sst_score = _sst_suitability(live_sst)
        if live_sst_score is not None:
            components.append((0.20, live_sst_score))
            details["live_sst"] = live_sst_score

        live_chl_score = _scale_score(live_chl, chl_low, chl_high)
        if live_chl_score is not None:
            components.append((0.20, live_chl_score))
            details["live_chlorophyll"] = live_chl_score

        if history:
            components.append((0.15, float(history["sst_score"])))
            details["historical_sst"] = round(float(history["sst_score"]), 1)
            components.append((0.15, float(history["chlorophyll_score"])))
            details["historical_chlorophyll"] = round(
                float(history["chlorophyll_score"]), 1
            )

        total_weight = sum(weight for weight, _ in components) or 1.0
        score = sum(weight * value for weight, value in components) / total_weight

        reasons: List[str] = []
        if live_sst is not None and live_sst_score is not None:
            reasons.append(
                f"live SST {live_sst:.2f}°C (suitability {live_sst_score:.0f}/100)"
            )
        if live_chl is not None and live_chl_score is not None:
            reasons.append(
                f"live chlorophyll {live_chl:.3f} mg/m³ (productivity {live_chl_score:.0f}/100)"
            )
        if history:
            reasons.append(
                f"historical {history['sst_mean_c']:.2f}°C SST mean (2007–2012)"
            )
            reasons.append(
                f"historical {history['chlorophyll_mean_mg_m3']:.3f} mg/m³ chlorophyll mean (2007–2012)"
            )
        reasons.append(f"{distance:.1f} km from your location")

        ranked.append(
            {
                "distance_km": round(distance, 1),
                "rank_score": round(max(0.0, min(100.0, score)), 1),
                "from_coast": record.get("From the coast of", ""),
                "direction": record.get("Direction", ""),
                "bearing_deg": record.get("Bearing (deg)"),
                "distance_advisory_km": record.get("Distance (km) From-To", ""),
                "depth_m": record.get("Depth (mtr) From-To", ""),
                "lat": pfz_lat,
                "lon": pfz_lon,
                "state": record.get("State", ""),
                "forecast_validity": record.get("Forecast_Validity", ""),
                "reasons": reasons,
                "live_sst_c": live_sst,
                "live_chlorophyll_mg_m3": live_chl,
                "historical_sst_mean_c": (
                    round(history["sst_mean_c"], 3) if history else None
                ),
                "historical_chlorophyll_mean_mg_m3": (
                    round(history["chlorophyll_mean_mg_m3"], 4)
                    if history
                    else None
                ),
                "score_components": details,
            }
        )

    ranked.sort(key=lambda item: (-item["rank_score"], item["distance_km"]))
    limited = ranked[:max_results]
    for rank, item in enumerate(limited, 1):
        item["rank"] = rank

    return {
        "status": "OK",
        "user_location": {"lat": lat, "lon": lon},
        "generated_at": now.isoformat(),
        "live_conditions": marine,
        "results": limited,
        "method": (
            "PFZ ranking uses 20% proximity + 10% advisory freshness + 20% live SST + "
            "20% live chlorophyll + 15% historical SST + 15% historical chlorophyll. "
            "Historical SST/chlorophyll use the repository's synthetic 2007–2012 coastal "
            "series; live SST uses NASA/JPL MUR via NOAA ERDDAP and live chlorophyll uses "
            "NOAA VIIRS via CoastWatch ERDDAP. Decision support only; not a guarantee of fish presence."
        ),
        "sources": {
            "pfz_advisories": "orca-backend/data/pfz_advisories.csv",
            "historical_environment": "orca-backend/data/synthetic_indian_coastal_sst_chlorophyll_2007_2012.csv",
            "satellite_sst": "NASA/JPL MUR via NOAA ERDDAP",
            "satellite_chlorophyll": "NOAA VIIRS via CoastWatch ERDDAP",
            "marine_conditions": "Open-Meteo Marine",
        },
    }
