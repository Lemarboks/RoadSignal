from bootstrap import request

route = request("http://valhalla:8002/route", {
    "locations": [{"lat": -33.9249, "lon": 18.4241}, {"lat": -33.9706, "lon": 18.5973}],
    "costing": "auto", "units": "kilometers", "shape_format": "polyline6",
})
trip = route["trip"]
assert trip["status"] == 0 and trip["summary"]["length"] > 10
assert trip["legs"][0]["shape"]
print({"valhalla": "passed", "region": "Western Cape", "distance_km": round(trip["summary"]["length"], 2),
       "data": "OpenStreetMap road graph, not live traffic"})
