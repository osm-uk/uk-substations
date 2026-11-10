from inspire_polygons import InspirePolygons

def test_live_local_authorities():
    polygons = InspirePolygons()
    assert len(polygons.published_date) > 0
