# Hermes skills tap

Public [Hermes Agent](https://github.com/NousResearch/hermes-agent) skill tap.

| Skill | What it does |
|---|---|
| [`weather-open-meteo`](skills/weather-open-meteo/SKILL.md) | Current weather + 1-7 day forecast for any city via Open-Meteo. No API key, standard-library Python. |

## Install

```bash
hermes skills tap add <org-name>/hermes-skills
hermes skills install <org-name>/hermes-skills/weather-open-meteo
```

Try it without Hermes: `python3 skills/weather-open-meteo/scripts/weather.py "Los Angeles, CA" --days 3`

Weather data: [Open-Meteo](https://open-meteo.com/) (free, CC BY 4.0). License: MIT.
