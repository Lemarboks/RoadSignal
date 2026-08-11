import httpx


class OpenMeteoWeatherProvider:
    """Turns current Open-Meteo conditions into a transparent route-risk penalty."""

    def __init__(self, url: str, timeout: float):
        self.url = url
        self.timeout = timeout

    async def penalty(self, latitude: float, longitude: float) -> tuple[float, list[str]]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
                response = await client.get(
                    self.url,
                    params={
                        "latitude": latitude,
                        "longitude": longitude,
                        "current": "precipitation,weather_code,wind_speed_10m,visibility",
                        "timezone": "auto",
                    },
                )
                response.raise_for_status()
                current = response.json().get("current", {})
        except (httpx.HTTPError, ValueError, TypeError):
            return 0.0, []

        precipitation = float(current.get("precipitation") or 0)
        wind = float(current.get("wind_speed_10m") or 0)
        visibility = float(current.get("visibility") or 10_000)
        code = int(current.get("weather_code") or 0)
        penalty = min(18.0, precipitation * 2.5 + max(0, wind - 35) * 0.15 + max(0, 5000 - visibility) / 600)
        if code >= 95:
            penalty = min(20.0, penalty + 8)
        factors = []
        if precipitation > 0.2: factors.append("Rain")
        if wind > 35: factors.append("Strong wind")
        if visibility < 5000: factors.append("Low visibility")
        if code >= 95: factors.append("Thunderstorm")
        return round(penalty, 1), factors
