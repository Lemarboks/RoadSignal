"""Inverse of the South African Lo coordinate system.

City of Cape Town service requests carry position as two fields in the
national Lo (Gauss conformal) system rather than as latitude/longitude:

    X_Y_Co_ordinate_1 = -3743793.17    X_Y_Co_ordinate_2 = -47667.49

The Lo system differs from ordinary transverse Mercator in two ways that
matter here: its axes are southing (positive south of the equator) and
westing (positive west of the belt's central meridian), and this dataset
stores both negated. Cape Town sits in the Lo19 belt, central meridian 19E.

That the belt is 19E is not assumed -- it is what the data says. Table View
lies 0.51 degrees west of 19E, which at that latitude is 47.2km, against a
stored westing of 47.67km; Khayelitsha's westing agrees the same way. A wrong
central meridian would put these points tens of kilometres into the sea.

Implemented with the standard footpoint-latitude series on the WGS84
ellipsoid, which Hartebeesthoek94 shares. No third-party projection library
is needed for a single belt at this accuracy.
"""
from __future__ import annotations

from math import atan, cos, degrees, radians, sin, sqrt, tan

# WGS84 / Hartebeesthoek94.
_A = 6378137.0
_F = 1 / 298.257223563
_B = _A * (1 - _F)
_E2 = (_A**2 - _B**2) / _A**2  # first eccentricity squared
_EP2 = (_A**2 - _B**2) / _B**2  # second eccentricity squared
_N = (_A - _B) / (_A + _B)

CAPE_TOWN_CENTRAL_MERIDIAN = 19.0
_SCALE = 1.0  # the Lo system uses a unit scale factor on the central meridian


def _meridian_arc(latitude: float) -> float:
    """Distance from the equator along the meridian, in metres."""
    n2, n3, n4 = _N**2, _N**3, _N**4
    a0 = 1 + n2 / 4 + n4 / 64
    a2 = 1.5 * (_N - n3 / 8)
    a4 = 0.9375 * (n2 - n4 / 4)
    a6 = 35 / 24 * n3
    return (_A / (1 + _N)) * (
        a0 * latitude - a2 * sin(2 * latitude) + a4 * sin(4 * latitude) - a6 * sin(6 * latitude)
    )


def _footpoint_latitude(northing: float) -> float:
    """Latitude whose meridian arc equals this northing, by iteration.

    Converges in a handful of passes at these magnitudes; the loop is bounded
    so a pathological input cannot hang a request.
    """
    latitude = northing / _A
    for _ in range(12):
        difference = northing - _meridian_arc(latitude)
        if abs(difference) < 1e-6:
            break
        # d(arc)/d(lat) is very nearly the meridian radius of curvature.
        latitude += difference * (1 - _E2 * sin(latitude) ** 2) ** 1.5 / (_A * (1 - _E2))
    return latitude


def lo_to_wgs84(
    southing: float, westing: float, central_meridian: float = CAPE_TOWN_CENTRAL_MERIDIAN
) -> tuple[float, float]:
    """Convert Lo southing/westing (metres, positive south and west) to
    (latitude, longitude) in degrees."""
    northing = -southing  # southing is positive southward
    easting = -westing  # westing is positive westward
    phi = _footpoint_latitude(northing / _SCALE)
    sin_phi, cos_phi, tan_phi = sin(phi), cos(phi), tan(phi)
    if abs(cos_phi) < 1e-12:  # a pole: no meaningful longitude
        return degrees(phi), central_meridian
    nu = _A / sqrt(1 - _E2 * sin_phi**2)
    rho = nu * (1 - _E2) / (1 - _E2 * sin_phi**2)
    psi = nu / rho
    x = easting / (_SCALE * nu)
    t2 = tan_phi**2
    # Latitude and longitude series, terms to x^6 -- far beyond what a street
    # address needs, and cheap.
    latitude = phi - (tan_phi / rho) * (easting**2 / (2 * _SCALE * nu)) * (1 / psi)
    latitude += (tan_phi / rho) * (easting**4 / (24 * _SCALE**3 * nu**3)) * (
        -4 * psi**2 + 9 * psi * (1 - t2) + 12 * t2
    )
    latitude -= (tan_phi / rho) * (easting**6 / (720 * _SCALE**5 * nu**5)) * (
        8 * psi**4 * (11 - 24 * t2)
        - 12 * psi**3 * (21 - 71 * t2)
        + 15 * psi**2 * (15 - 98 * t2 + 15 * t2**2)
        + 180 * psi * (5 * t2 - 3 * t2**2)
        + 360 * t2**2
    )
    omega = x - (x**3 / 6) * (psi + 2 * t2)
    omega += (x**5 / 120) * (-4 * psi**3 * (1 - 6 * t2) + psi**2 * (9 - 68 * t2) + 72 * psi * t2 + 24 * t2**2)
    longitude = central_meridian + degrees(omega / cos_phi)
    return degrees(latitude), longitude


def field_pair_to_wgs84(
    coordinate_1: float, coordinate_2: float, central_meridian: float = CAPE_TOWN_CENTRAL_MERIDIAN
) -> tuple[float, float] | None:
    """Convert the dataset's stored field pair, which negates both axes.

    Returns None for the 0,0 placeholder used on records with no location --
    roughly a quarter of the table -- rather than mapping them to a point in
    the Gulf of Guinea.
    """
    try:
        first, second = float(coordinate_1), float(coordinate_2)
    except (TypeError, ValueError):
        return None
    if not first or not second:
        return None
    latitude, longitude = lo_to_wgs84(-first, -second, central_meridian)
    return latitude, longitude
