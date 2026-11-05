# uk-substations

Locate potential local electricity substations in the UK

# description

Jez posits that substations mostly have their own small often square-ish cadastral parcel.
This code builds an environment to query UK cadastral parcel data via DuckDB to try to prove/disprove this assertion.

# usage

If you use VS Code or a related IDE the project will build a devcontainer for you.
Otherwise there is a Docker container and compose file.
From there, you can go to terminal and python with appropriate requirements will be available

'''python
from inspire_polygons import InspirePolygons
polygons = InspirePolygons()
print(polygons.published_date)
'''

Then you could either get every council in England and Wales in one go, which may take overnight depending on your download speed and memory,
or refer to a single county and the data will be downloaded and converted to parquet on demand.

'''python
parquet_path = polygons.parquet('Wiltshire_Council')
import duckdb
duckdb.sql("INSTALL spatial; LOAD spatial;")
duckdb.sql(f"SELECT ST_Area(geometry) as area, st_transform(geometry, 'EPSG:27700', 'EPSG:4326', always_xy := true) FROM '{parquet_path}' WHERE area > 12 and area < 15 LIMIT 5")
'''
