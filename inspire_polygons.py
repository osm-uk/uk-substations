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
        self.con.execute(f"""
            COPY (SELECT * FROM ST_Read('{vsizip}'))
            TO '{out_path}' (FORMAT parquet, COMPRESSION zstd)
        """)
        # quick check
        duckdb.sql(f'SELECT * FROM \'{out_path}\' LIMIT 5')

        return out_path

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