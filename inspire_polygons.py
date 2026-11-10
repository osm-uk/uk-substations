from bs4 import BeautifulSoup
from datetime import datetime
import dateutil.parser
from functools import cached_property
import duckdb
import os
import requests
import re


class InspirePolygons:
    root = 'https://use-land-property-data.service.gov.uk/datasets/inspire/download'
    con = duckdb.connect()
    con.install_extension("spatial")
    con.load_extension("spatial")
    con.install_extension("httpfs")
    con.load_extension("httpfs")
    con.execute("SET s3_region = 'us-west-2'")

    def download(self, local_authority):
        url = f'{self.root}/{local_authority}.zip'
        filename = f'tmp/{self.published_date}/{local_authority}.zip'
        if not os.path.exists(filename):
            print(f'downloading INSPIRE polygons from {url} to {filename}')
            filepath = f'tmp/{self.published_date}'
            os.makedirs(filepath, exist_ok=True)
            content = requests.get(url, stream=True).content
            with open(filename, 'wb') as out_file:
                out_file.write(content)

    def download_all(self):
        for local_authority in self.local_authorities:
            self.parquet(local_authority)

    @cached_property
    def local_authorities(self):
        las = []
        html_text = requests.get(self.root).text
        soup = BeautifulSoup(html_text, 'html.parser')
        for link in soup.find_all('a'):
            if link.get('data-ga-download'):
                local_authority = link.get('data-ga-download').replace('.zip', '')
                las.append(local_authority)
        return las

    def parquet(self, local_authority):
        filename = f'tmp/{self.published_date}/{local_authority}.zip'
        out_path = f'tmp/{self.published_date}/{local_authority}.parquet'
        if os.path.exists(out_path):
            # conversion already done
            return out_path

        if not os.path.exists(filename):
            self.download(local_authority)

        vsizip = f'/vsizip/{filename}/Land_Registry_Cadastral_Parcels.gml'
        print(f'converting gml from {vsizip} to {out_path}')
        selector = f"""
            SELECT
                *,
                ST_Transform(geometry, 'EPSG:27700', 'OGC:CRS84', always_xy := true) as crs84_geometry
            FROM ST_Read('{vsizip}')
        """
        self.con.execute(f"""
            COPY ({selector}')) TO '{out_path}' (FORMAT parquet, COMPRESSION zstd)
        """)
        # quick check
        duckdb.sql(f"SELECT * FROM '{out_path}' LIMIT 5")

        return out_path

    @cached_property
    def published_date(self):
        html_text = requests.get(self.root).text
        date_str = self.published_date_from_html(html_text)
        return date_str

    def published_date_from_html(self, html_text):
        soup = BeautifulSoup(html_text, 'html.parser')
        for paragraph in soup.find_all(string=re.compile('This dataset was published on')):
            date_str = re.search(r'(\d* \S* \d\d\d\d)', paragraph).group(1)
            date = dateutil.parser.parse(date_str)
            return datetime.strftime(date, '%Y%m%d')
        return

    def sql(self, select):
        local_authority = re.findall(r"FROM '(.*)'", select)[0]
        parquet = self.parquet(local_authority)
        select = re.sub(r"FROM '(.*)'", f"FROM '{parquet}'", select)
        print(self.con.sql(select))

    def substations(self, local_authority):
        print(self.con.sql(f"""
            SELECT
                ROUND(ST_Area(parcels.geometry), 0) as square_metres,
                ST_Centroid(parcels.crs84_geometry) as centroid,
                substations.name,
                ST_NPoints(parcels.geometry) as point_count,
                parcels.crs84_geometry
            FROM 'tmp/overture.parquet' as substations
            JOIN '{self.parquet(local_authority)}' as parcels
              ON ST_Contains(parcels.crs84_geometry, ST_Centroid(substations.geometry))
            WHERE square_metres > 12
              AND square_metres < 90
        """))

    def substation_sized_parcels(self, local_authority):
        print(self.con.sql(f"""
            SELECT
                ROUND(ST_Area(parcels.geometry), 0) as square_metres,
                ST_Centroid(parcels.crs84_geometry) as centroid,
                IF(ST_NPoints(parcels.geometry) = 5, true, false) as is_rectangle
            FROM '{self.parquet(local_authority)}' as parcels
            LEFT OUTER JOIN 'tmp/overture.parquet' as substations
              ON ST_Contains(parcels.crs84_geometry, ST_Centroid(substations.geometry))
            WHERE substations.geometry IS NULL
              AND square_metres > 20
              AND square_metres < 80
              AND is_rectangle
            ORDER BY square_metres
        """))
