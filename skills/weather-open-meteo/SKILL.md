---
name: weather-open-meteo
description: Current weather and a 1-7 day forecast for any city via Open-Meteo. Free, no API key, standard-library Python.
version: 1.0.0
author: hermes-skills contributors
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [weather, forecast, open-meteo, no-api-key]
    category: productivity
    requires_toolsets: [terminal]
---

# Weather (Open-Meteo)

## When to Use
- The user asks about weather, temperature, rain, or what to wear, for a named place or coordinates.
- A morning briefing needs today's weather.

## Procedure
1. Work out the place. If the user gave none, use the home city from memory/USER.md; if unknown, ask.
2. If a `weather_forecast` tool is available, call it (it runs this same script). Otherwise run the script
   (`SKILL_DIR` is the directory containing this SKILL.md):
   ```bash
   python3 SKILL_DIR/scripts/weather.py "Los Angeles, CA" --days 3
   ```
   Options: `--units metric` for °C/km/h (default is US units), `--lat 34.02 --lon -118.29` to skip geocoding,
   `--days 1-7`.
3. The script prints one JSON object: `place`, `now` (conditions, temperature, feels_like, wind) and `daily`
   (date, conditions, high, low, rain_chance).
4. Answer in 2-4 short lines: now, today's high/low and rain chance, one practical tip (umbrella, jacket).
   Mention the place the script resolved, so a wrong match is visible.

## Pitfalls
- Ambiguous names ("Springfield"): add the state or country, e.g. `"Springfield, IL"`.
- `{"success": false}`: the place was not found or Open-Meteo was unreachable. Say so; do not guess.
- Forecast times are in the place's own time zone (`timezone` field).

## Verification
`python3 SKILL_DIR/scripts/weather.py "Los Angeles, CA" --days 1` prints `"success": true` and a place label.
