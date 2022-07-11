from netCDF4 import Dataset
import numpy as np
import pandas as pd
from time import perf_counter
import datetime
from io import StringIO

from django.core.management.base import BaseCommand
from django.conf import settings
from django.db import connection


class Command(BaseCommand):
    help = '''
    Get a very plain CSV data provided by Adrien and publish it into the DB
    The data are the reference data for the flow values. They cover the period 2010-2020.
    Rows are dates, startin 2010-01-01. The columns are stations, in the right order (hope so)
    '''

    # Class-wide variables, that will be set using env var or command options
    filepath         = None
    db_connect_url   = None
    db_schema        = None

    def add_arguments(self, parser):
        parser.add_argument('-p', '--path',
                            help='path the the CSV file')
        parser.add_argument('-d', '--db_connect_url',
                            default=settings.SAGUI_SETTINGS.get('HYFAA_DATABASE_URI', None),
                            help='The connection URL for the DB. (Default: "postgresql://postgres:sagui@localhost:5432/sagui")')
        parser.add_argument('-s', '--schema',
                            default=settings.SAGUI_SETTINGS.get('HYFAA_DATABASE_SCHEMA', 'hyfaa'),
                            help='DB schema (Default: "hyfaa")')

    def handle(self, *args, **kwargs):
        tic = perf_counter()

        self.filepath = kwargs['path']
        self.db_connect_url = kwargs.get('db_connect_url')
        self.db_schema = kwargs.get('schema')

        # load the CSV data: each column is a station, each row a date, starting 2010-01-01
        df = pd.read_csv(self.filepath, sep=';', header=None)
        # Name columns (to ID of the station)
        columns = [str(i) for i in range(1, len(df.columns) + 1)]
        df.columns = columns

        # Insert a date columns
        base = datetime.datetime.strptime('2010-01-01', "%Y-%m-%d")
        date_list = [base + datetime.timedelta(days=x) for x in range(len(df))]
        df.insert(0, 'date', date_list)

        # insert a day of the year column
        df['doy'] = df["date"].dt.dayofyear

        # Group and take the mean
        df_means_by_doy = df.groupby('doy').mean().round()

        # Stack it into k,v form
        df2 = df_means_by_doy.stack().reset_index()
        df2.columns = ['day_of_year', 'station_id', 'value']
        # convert value column to smallinteger type
        df2['value']= df2['value'].apply(np.int16)

        # Save to CSV file
        # df2.to_csv('/tmp/df2.csv', index=False)

        # save dataframe to an in memory buffer, cf https://naysan.ca/2020/05/09/pandas-to-postgresql-using-psycopg2-bulk-insert-performance-benchmark/
        buffer = StringIO()
        df2.to_csv(buffer, header=False, index=True)
        buffer.seek(0)

        # Execute the query
        with connection.cursor() as cursor:
            cursor.copy_from(buffer, 'stations_reference_flow', sep=",")

        # Publish to DB
        # df2.to_sql('stations_reference_flow',
        #            self.db_connect_url,
        #            schema=self.db_schema,
        #            index=False,
        #            if_exists='replace',
        #            chunksize=1000,
        #            dtype=['i2', 'i2', 'i2'],
        #            method='multi')

        tac = perf_counter()
        self.stdout.write(self.style.SUCCESS('Total processing time: {}'.format(tac - tic)))

