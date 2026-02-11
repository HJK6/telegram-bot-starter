"""
Weather ability — free, no API key required.

Uses Open-Meteo geocoding + forecast APIs.
"""

import requests

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


def _geocode(city: str) -> dict:
    resp = requests.get(GEO_URL, params={"name": city, "count": 1}, timeout=10)
    resp.raise_for_status()
    results = resp.json().get("results")
    if not results:
        raise ValueError(f"City not found: {city}")
    return results[0]


def get_weather(city: str) -> str:
    """Get current weather for a city. Returns a formatted string."""
    geo = _geocode(city)
    lat, lon = geo["latitude"], geo["longitude"]
    name = geo.get("name", city)
    country = geo.get("country", "")

    resp = requests.get(
        WEATHER_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "current_weather": True,
            "temperature_unit": "fahrenheit",
            "windspeed_unit": "mph",
        },
        timeout=10,
    )
    resp.raise_for_status()
    cw = resp.json()["current_weather"]

    return (
        f"Weather for {name}, {country}\n"
        f"Temp: {cw['temperature']}°F\n"
        f"Wind: {cw['windspeed']} mph\n"
        f"Conditions: WMO code {cw['weathercode']}"
    )
