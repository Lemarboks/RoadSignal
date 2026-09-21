"""Sunrise, sunset and darkness for a place and time.

A reported street-light outage is a hazard at 21:00 and irrelevant at noon,
so the outage layer has to know whether the trip happens after dark. This is
computed rather than fetched: it needs no API, no key and no network, and the
API already collects a departure time.

Uses the NOAA solar position approximation, accurate to well under a minute
for these latitudes -- far tighter than a risk baseline requires.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import acos, asin, cos, degrees, radians, sin, tan

# Civil twilight rather than geometric sunset: the sun sits 6 degrees below
# the horizon, which is roughly when street lighting starts to matter.
CIVIL_TWILIGHT_DEGREES = -6.0
_SUNSET_DEGREES = -0.833  # includes refraction and the solar disc


def _fractional_year(when: datetime) -> float:
    day_of_year = when.timetuple().tm_yday
    return 2 * 3.141592653589793 / 365 * (day_of_year - 1 + (when.hour - 12) / 24)


def _equation_of_time(gamma: float) -> float:
    """Minutes by which apparent solar time leads mean solar time."""
    return 229.18 * (
        0.000075
        + 0.001868 * cos(gamma)
        - 0.032077 * sin(gamma)
        - 0.014615 * cos(2 * gamma)
        - 0.040849 * sin(2 * gamma)
    )


def _declination(gamma: float) -> float:
    return (
        0.006918
        - 0.399912 * cos(gamma)
        + 0.070257 * sin(gamma)
        - 0.006758 * cos(2 * gamma)
        + 0.000907 * sin(2 * gamma)
        - 0.002697 * cos(3 * gamma)
        + 0.00148 * sin(3 * gamma)
    )


def solar_elevation(latitude: float, longitude: float, when: datetime) -> float:
    """Sun elevation above the horizon, in degrees. Negative is below."""
    when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    when = when.astimezone(timezone.utc)
    gamma = _fractional_year(when)
    declination = _declination(gamma)
    minutes = when.hour * 60 + when.minute + when.second / 60
    true_solar_time = minutes + _equation_of_time(gamma) + 4 * longitude
    hour_angle = radians(true_solar_time / 4 - 180)
    phi = radians(latitude)
    zenith = acos(
        min(1.0, max(-1.0, sin(phi) * sin(declination) + cos(phi) * cos(declination) * cos(hour_angle)))
    )
    return 90 - degrees(zenith)


def _event(latitude: float, longitude: float, when: datetime, angle: float, sunset: bool):
    """Time the sun crosses `angle`, on the date of `when` (UTC)."""
    when = when if when.tzinfo else when.replace(tzinfo=timezone.utc)
    when = when.astimezone(timezone.utc)
    gamma = _fractional_year(when.replace(hour=12, minute=0, second=0, microsecond=0))
    declination = _declination(gamma)
    phi = radians(latitude)
    cos_hour_angle = (
        cos(radians(90 - angle)) - sin(phi) * sin(declination)
    ) / (cos(phi) * cos(declination))
    if cos_hour_angle > 1 or cos_hour_angle < -1:
        return None  # polar day or night: the sun never crosses this angle
    hour_angle = degrees(acos(cos_hour_angle))
    offset = hour_angle if sunset else -hour_angle
    minutes = 720 + 4 * (offset - longitude) - _equation_of_time(gamma)
    midnight = when.replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight + timedelta(minutes=minutes)


def sunset(latitude: float, longitude: float, when: datetime) -> datetime | None:
    return _event(latitude, longitude, when, _SUNSET_DEGREES, sunset=True)


def sunrise(latitude: float, longitude: float, when: datetime) -> datetime | None:
    return _event(latitude, longitude, when, _SUNSET_DEGREES, sunset=False)


def is_dark(latitude: float, longitude: float, when: datetime) -> bool:
    """True when the sun is below civil twilight -- lighting matters."""
    return solar_elevation(latitude, longitude, when) < CIVIL_TWILIGHT_DEGREES


def darkness_factor(latitude: float, longitude: float, when: datetime) -> float:
    """0 in daylight, rising to 1 in full darkness.

    Ramped rather than switched: dusk is not the same as midnight, and a hard
    boundary would make a score jump by a minute's difference in departure.
    """
    elevation = solar_elevation(latitude, longitude, when)
    if elevation >= 0:
        return 0.0
    if elevation <= CIVIL_TWILIGHT_DEGREES:
        return 1.0
    return round(elevation / CIVIL_TWILIGHT_DEGREES, 3)
