#!/usr/bin/env python3
"""Current weather + short forecast from Open-Meteo (free, no API key). Standard library only.
If Open-Meteo's forecast server does not answer (it times out from some cloud networks), the same place is
looked up in MET Norway's free API (api.met.no) instead; the output format is identical, "source" says which.

    python3 weather.py "Los Angeles, CA"            # US units (F, mph)
    python3 weather.py "Berlin" --days 3 --units metric
    python3 weather.py --lat 34.02 --lon -118.29    # skip geocoding
Prints one JSON object; on failure prints {"success": false, "error": ...} and exits 1.
"""

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST = "https://api.open-meteo.com/v1/forecast"
MET = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
MET_USER_AGENT = "weather-open-meteo-skill/1.1 (Hermes skill; github.com hermes-skills)"   # required by MET
OPEN_METEO_TIMEOUT_S = 6
# MET Norway symbol codes (minus _day/_night/_polartwilight) -> the WMO codes used below.
MET_SYMBOLS = {"clearsky": 0, "fair": 1, "partlycloudy": 2, "cloudy": 3, "fog": 45, "lightrain": 61, "rain": 63,
               "heavyrain": 65, "lightrainshowers": 80, "rainshowers": 81, "heavyrainshowers": 82,
               "lightsleet": 66, "sleet": 66, "heavysleet": 67, "lightsleetshowers": 66, "sleetshowers": 66,
               "lightsnow": 71, "snow": 73, "heavysnow": 75, "lightsnowshowers": 85, "snowshowers": 85,
               "heavysnowshowers": 86}
WMO = {0: "clear", 1: "mainly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "freezing fog",
       51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 56: "freezing drizzle", 57: "freezing drizzle",
       61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
       71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains", 80: "rain showers",
       81: "rain showers", 82: "violent rain showers", 85: "snow showers", 86: "snow showers",
       95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail"}


def get(url: str, params: dict) -> dict:
    timeout = OPEN_METEO_TIMEOUT_S if url == FORECAST else 20
    with urllib.request.urlopen(f"{url}?{urllib.parse.urlencode(params)}", timeout=timeout) as response:
        return json.load(response)


def get_met(params: dict) -> dict:
    request = urllib.request.Request(f"{MET}?{urllib.parse.urlencode(params)}",
                                     headers={"User-Agent": MET_USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def geocode(place: str) -> dict:
    name, *hints = [p.strip() for p in place.split(",") if p.strip()]
    results = get(GEOCODE, {"name": name, "count": 10, "language": "en", "format": "json"}).get("results") or []
    if not results:
        raise LookupError(f"place not found: {place}")
    for hint in (h.lower() for h in hints):
        matching = [r for r in results if hint in " ".join(
            str(r.get(k, "")) for k in ("admin1", "country", "country_code")).lower()
            or (len(hint) == 2 and hint.upper() == r.get("admin1_code", ""))]
        results = matching or results
    best = results[0]
    label = ", ".join(str(best[k]) for k in ("name", "admin1", "country") if best.get(k))
    return {"lat": best["latitude"], "lon": best["longitude"], "label": label, "tz": best.get("timezone")}


def forecast(lat: float, lon: float, days: int, metric: bool, tz: str | None = None) -> dict:
    try:
        return forecast_open_meteo(lat, lon, days, metric)
    except (OSError, ValueError):                       # URLError/timeouts are OSError subclasses
        return met_as_open_meteo(get_met({"lat": round(lat, 4), "lon": round(lon, 4)}), tz, days, metric)


def met_symbol(symbol: str | None) -> int | None:
    if not symbol:
        return None
    base = symbol.split("_")[0]
    return 95 if "thunder" in base else MET_SYMBOLS.get(base)


def met_as_open_meteo(data: dict, tz: str | None, days: int, metric: bool) -> dict:
    """Convert MET Norway's timeseries (UTC, Celsius, m/s, mm) into the Open-Meteo shape summarize() reads."""
    zone = ZoneInfo(tz) if tz else UTC
    temp = (lambda c: round(c, 1)) if metric else (lambda c: round(c * 9 / 5 + 32, 1))
    wind = (lambda ms: round(ms * 3.6, 1)) if metric else (lambda ms: round(ms * 2.23694, 1))
    rain = (lambda mm: round(mm, 1)) if metric else (lambda mm: round(mm / 25.4, 2))
    series = data["properties"]["timeseries"]
    per_day: dict[str, dict] = {}
    for entry in series:
        local = datetime.fromisoformat(entry["time"]).astimezone(zone)
        day = per_day.setdefault(local.date().isoformat(), {"temps": [], "rain": 0.0, "symbols": Counter()})
        details = entry["data"]["instant"]["details"]
        day["temps"].append(details["air_temperature"])
        window = entry["data"].get("next_1_hours") or entry["data"].get("next_6_hours") or {}
        day["rain"] += window.get("details", {}).get("precipitation_amount", 0.0)
        if 9 <= local.hour <= 18 and window.get("summary"):
            day["symbols"][window["summary"]["symbol_code"]] += 1
    first, dates = series[0], sorted(per_day)[:days]
    now_window = first["data"].get("next_1_hours") or first["data"].get("next_6_hours") or {}
    now_temp = temp(first["data"]["instant"]["details"]["air_temperature"])
    return {"timezone": tz or "UTC", "_source": "MET Norway (api.met.no) - Open-Meteo forecast unavailable",
            "current": {"time": datetime.fromisoformat(first["time"]).astimezone(zone)
                        .strftime("%Y-%m-%dT%H:%M"), "temperature_2m": now_temp, "apparent_temperature": now_temp,
                        "weather_code": met_symbol(now_window.get("summary", {}).get("symbol_code")),
                        "wind_speed_10m": wind(first["data"]["instant"]["details"].get("wind_speed", 0.0))},
            "daily": {"time": dates,
                      "weather_code": [met_symbol(per_day[d]["symbols"].most_common(1)[0][0])
                                       if per_day[d]["symbols"] else None for d in dates],
                      "temperature_2m_max": [temp(max(per_day[d]["temps"])) for d in dates],
                      "temperature_2m_min": [temp(min(per_day[d]["temps"])) for d in dates],
                      "precipitation_probability_max": [None for _ in dates],
                      "precipitation_sum": [rain(per_day[d]["rain"]) for d in dates]}}


def forecast_open_meteo(lat: float, lon: float, days: int, metric: bool) -> dict:
    params = {"latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": days,
              "current": "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
              "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"}
    if not metric:
        params.update(temperature_unit="fahrenheit", wind_speed_unit="mph", precipitation_unit="inch")
    return get(FORECAST, params)


def summarize(raw: dict, label: str, metric: bool) -> dict:
    t, w, r = ("°C", "km/h", "mm") if metric else ("°F", "mph", "in")
    cur, daily = raw.get("current", {}), raw.get("daily", {})
    days = [{"date": d, "conditions": WMO.get(code, "unknown"), "high": f"{hi}{t}", "low": f"{lo}{t}",
             "rain_chance": f"{p}%" if p is not None else "n/a"}
            for d, code, hi, lo, p in zip(daily.get("time", []), daily.get("weather_code", []),
                                          daily.get("temperature_2m_max", []), daily.get("temperature_2m_min", []),
                                          daily.get("precipitation_probability_max", []))]
    for day, amount in zip(days, daily.get("precipitation_sum", [])):
        day["precipitation"] = f"{amount} {r}"
    return {"success": True, "place": label, "timezone": raw.get("timezone"),
            "now": {"time": cur.get("time"), "conditions": WMO.get(cur.get("weather_code"), "unknown"),
                    "temperature": f"{cur.get('temperature_2m')}{t}",
                    "feels_like": f"{cur.get('apparent_temperature')}{t}", "wind": f"{cur.get('wind_speed_10m')} {w}"},
            "daily": days, "source": raw.get("_source", "Open-Meteo (open-meteo.com)")}


def lookup(place: str | None = None, lat: float | None = None, lon: float | None = None, days: int = 3,
           units: str = "us") -> dict:
    """Library entry point (also used by my Hermes plugin's weather_forecast tool)."""
    metric = units == "metric"
    if lat is not None and lon is not None:
        where = {"lat": lat, "lon": lon, "label": f"{lat},{lon}", "tz": None}
    elif place:
        where = geocode(place)
    else:
        raise ValueError("give a place or --lat/--lon")
    raw = forecast(where["lat"], where["lon"], max(1, min(days, 7)), metric, where.get("tz"))
    return summarize(raw, where["label"], metric)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("place", nargs="?", help='City, optionally with region/country: "Austin, TX"')
    parser.add_argument("--lat", type=float)
    parser.add_argument("--lon", type=float)
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--units", choices=["us", "metric"], default="us")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(lookup(args.place, args.lat, args.lon, args.days, args.units), ensure_ascii=False))
        return 0
    except (urllib.error.URLError, LookupError, ValueError, KeyError) as error:
        print(json.dumps({"success": False, "error": str(error)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
