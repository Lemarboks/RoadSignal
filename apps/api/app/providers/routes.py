from abc import ABC, abstractmethod

class RouteProvider(ABC):
    @abstractmethod
    async def alternatives(self, origin: str, destination: str) -> list[dict]: ...

class MockCapeTownRouteProvider(RouteProvider):
    async def alternatives(self, origin: str, destination: str) -> list[dict]:
        return [
            {"id":"route-balanced","name":"Balanced Route","duration_minutes":29,"distance_km":18.7,"geometry":[[-33.9249,18.4241],[-33.936,18.443],[-33.951,18.473],[-33.970,18.505],[-33.981,18.531]]},
            {"id":"route-safest","name":"Safest Route","duration_minutes":33,"distance_km":20.4,"geometry":[[-33.9249,18.4241],[-33.918,18.455],[-33.931,18.489],[-33.955,18.520],[-33.981,18.531]]},
            {"id":"route-fastest","name":"Fastest Route","duration_minutes":24,"distance_km":17.1,"geometry":[[-33.9249,18.4241],[-33.941,18.452],[-33.963,18.478],[-33.976,18.505],[-33.981,18.531]]},
        ]

class AzureMapsRouteProvider(RouteProvider):
    def __init__(self, key: str): self.key = key
    async def alternatives(self, origin: str, destination: str) -> list[dict]:
        raise RuntimeError("Azure provider requires deployment adapter configuration; use ROUTE_PROVIDER=mock locally")
