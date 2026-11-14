#!/usr/bin/env python3
"""Current weather + short forecast from Open-Meteo (free, no API key). Standard library only.

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

GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST = "https://api.open-meteo.com/v1/forecast"
WMO = {0: "clear", 1: "mainly clear", 2: "partly cloudy", 3: "overcast", 45: "fog", 48: "freezing fog",
       51: "light drizzle", 53: "drizzle", 55: "heavy drizzle", 56: "freezing drizzle", 57: "freezing drizzle",
       61: "light rain", 63: "rain", 65: "heavy rain", 66: "freezing rain", 67: "freezing rain",
       71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains", 80: "rain showers",
       81: "rain showers", 82: "violent rain showers", 85: "snow showers", 86: "snow showers",
       95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with hail"}


def get(url: str, params: dict) -> dict:
    with urllib.request.urlopen(f"{url}?{urllib.parse.urlencode(params)}", timeout=20) as response:
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
    return {"lat": best["latitude"], "lon": best["longitude"], "label": label}


def forecast(lat: float, lon: float, days: int, metric: bool) -> dict:
    params = {"latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": days,
              "current": "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m",
              "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"}
    if not metric:
        params.update(temperature_unit="fahrenheit", wind_speed_unit="mph", precipitation_unit="inch")
    return get(FORECAST, params)


def summarize(raw: dict, label: str, metric: bool) -> dict:
    t, w = ("°C", "km/h") if metric else ("°F", "mph")
    cur, daily = raw.get("current", {}), raw.get("daily", {})
    days = [{"date": d, "conditions": WMO.get(code, f"code {code}"), "high": f"{hi}{t}", "low": f"{lo}{t}",
             "rain_chance": f"{p}%" if p is not None else "n/a"}
            for d, code, hi, lo, p in zip(daily.get("time", []), daily.get("weather_code", []),
                                          daily.get("temperature_2m_max", []), daily.get("temperature_2m_min", []),
                                          daily.get("precipitation_probability_max", []))]
    return {"success": True, "place": label, "timezone": raw.get("timezone"),
            "now": {"time": cur.get("time"), "conditions": WMO.get(cur.get("weather_code"), "unknown"),
                    "temperature": f"{cur.get('temperature_2m')}{t}",
                    "feels_like": f"{cur.get('apparent_temperature')}{t}", "wind": f"{cur.get('wind_speed_10m')} {w}"},
            "daily": days, "source": "Open-Meteo (open-meteo.com)"}


def lookup(place: str | None = None, lat: float | None = None, lon: float | None = None, days: int = 3,
           units: str = "us") -> dict:
    """Library entry point (also used by my Hermes plugin's weather_forecast tool)."""
    metric = units == "metric"
    if lat is not None and lon is not None:
        where = {"lat": lat, "lon": lon, "label": f"{lat},{lon}"}
    elif place:
        where = geocode(place)
    else:
        raise ValueError("give a place or --lat/--lon")
    raw = forecast(where["lat"], where["lon"], max(1, min(days, 7)), metric)
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
