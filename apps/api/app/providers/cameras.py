"""Camera source selection.

Mirrors the ResilientRouteProvider pattern already used for routing: prefer the
authoritative source, fall back to the alternative, and report which one
actually answered so the UI never presents an empty layer as a real answer.

The official i-TRAFFIC developer API is preferred because it is the data owner
and the sanctioned route. opencctv.org is retained only as a fallback for
deployments with no developer key -- it is an aggregator that re-published the
same data and currently returns 403 after putting its API behind auth, so it is
expected to fail. It is kept rather than deleted because it needs no key, and
if it reopens a keyless deployment gets cameras again for free.
"""
from __future__ import annotations


class ResilientCameraProvider:
    def __init__(self, primary, fallback):
        self.primary = primary
        self.fallback = fallback
        self._last_source: str | None = None
        # Reachability is only meaningful after an attempt. Providers start
        # optimistically, so reporting their default would claim the layer is
        # healthy before anything has been fetched -- the exact confusion this
        # whole change exists to remove.
        self._attempted = False

    @property
    def last_source(self) -> str | None:
        return self._last_source

    @property
    def source(self) -> str:
        if self._last_source:
            return self._last_source
        return "i-traffic.co.za" if getattr(self.primary, "configured", False) else "opencctv.org"

    @property
    def reachable(self) -> bool:
        if not self._attempted:
            # Nothing tried yet: only claim health if a source is even usable.
            return bool(getattr(self.primary, "configured", False))
        return self._last_source is not None

    @property
    def last_error(self) -> str | None:
        """The reason worth showing an operator.

        When the official API is unconfigured, that is the actionable problem --
        not whatever the deprecated aggregator happened to return.
        """
        if not getattr(self.primary, "configured", False):
            primary_reason = getattr(self.primary, "last_error", None)
            fallback_reason = getattr(self.fallback, "last_error", None)
            if fallback_reason:
                return f"{primary_reason}; fallback {fallback_reason}"
            return primary_reason
        return getattr(self.primary, "last_error", None)

    async def cameras(self) -> list[dict]:
        self._attempted = True
        if getattr(self.primary, "configured", False):
            cameras = await self.primary.cameras()
            if getattr(self.primary, "reachable", False):
                self._last_source = "i-traffic.co.za"
                return cameras
        cameras = await self.fallback.cameras()
        # A reachable fallback counts even when it returns nothing: "the source
        # answered and the region is empty" is a real answer.
        self._last_source = "opencctv.org" if getattr(self.fallback, "reachable", False) else None
        return cameras
