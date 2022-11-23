"""
Utilities related to Stations reference data. They are flow data from pre-global warming period,
that we use to compare with the current flow values
"""

from django.db import connection
from django.db.backends.utils import CursorWrapper

import pandas as pd
import numpy as np
from contextlib import contextmanager
from io import StringIO
from typing import Any

from .. import models

# Used in next function, to encapsulate the SQL copy command in a with block that handles
# the temp table
# Inspired from https://www.thebookofjoel.com/django-fast-bulk-upsert
@contextmanager
def setup_teardown_temp_tables(cursor: CursorWrapper):
    """Context manager for creating and dropping temp tables"""
    cursor.execute(
        '''
        DROP TABLE IF EXISTS stations_reference_flow_temp;
        CREATE  TABLE stations_reference_flow_temp AS SELECT id, period_id, station_id, day_of_year, "value" FROM stations_reference_flow LIMIT 0;
        '''
    )
    try:
        yield
    finally:
        cursor.execute(
            '''
            DROP TABLE IF EXISTS stations_reference_flow_temp;
            '''
        )


def import_csv(csv_file: Any):
    """
    Parse a CSV data file and try to import as much as possible into the DB (table stations_reference_flow)
    Expected content for the csv file is
        target_period;date;1;2;3;4;5;6;7;8;9;10;11;12;13
        2010-2020;01/01/10;110;226;497;66;75;34;31;122;284;54;5;19;9
        2010-2020;02/01/10;120;150;382;91;75;44;37;81;205;33;4;9;9
        2010-2020;03/01/10;150;163;303;102;94;39;54;145;196;34;14;6;18
        2010-2020;04/01/10;165;198;350;106;109;31;74;236;296;57;12;15;20
        ...
    target_period should already exist in the DB table stations_reference_flow_period
    :param csv_file: can be any input accepted by pandas read_csv function: file path, stream, ByteIO
    :return:
    """
    # Get list of available periods (declared in UI/DB)
    periods = models.StationsReferenceFlowPeriod.objects.all().values()
    period_names = [p['period'] for p in periods]
    # Get list of station ids (only allow to try to import those)
    stations = models.Stations.objects.values('id', 'name').order_by('id')
    stations_ids = [s['id'] for s in stations]
    df = pd.read_csv(csv_file, sep=';', parse_dates=['date'],
                     dayfirst=True, dtype={'target_period': "string", 'station_id': 'int16'})

    # filter out periods that are not valid (not declared)
    df.query("target_period in " + str(period_names), inplace=True)

    # insert a day of the year column
    df['doy'] = df["date"].dt.dayofyear

    # Group and take the mean
    df_means_by_doy = df.groupby(['target_period', 'doy']).mean().round()

    # Stack it into k,v form
    df2 = df_means_by_doy.stack().reset_index()
    df2.columns = ['target_period', 'day_of_year', 'station_id', 'value']
    # convert value column to smallinteger type
    df2['station_id'] = df2['station_id'].apply(np.int16)
    df2['value'] = df2['value'].apply(np.int16)

    # filter out stations that do not exist in the DB
    df2.query("station_id in " + str(stations_ids), inplace=True)

    # Replace the target_periods column par a column with period_id referring to the periods table
    p = {i['period']: i['id'] for i in periods}
    df2['period_id'] = df2['target_period'].map(p)
    df2.drop('target_period', axis=1, inplace=True)

    # Save to CSV file
    # df2.to_csv('/tmp/df2.csv', index=False)

    # save dataframe to an in memory buffer, cf https://naysan.ca/2020/05/09/pandas-to-postgresql-using-psycopg2-bulk-insert-performance-benchmark/
    buffer = StringIO()
    df2.to_csv(buffer, columns=['period_id', 'station_id', 'day_of_year', 'value'], header=False, index=True)
    buffer.seek(0)
    # Write the data into the DB using copy from and an upsert query
    # Inspired from https://www.thebookofjoel.com/django-fast-bulk-upsert
    with connection.cursor() as cursor:
        with setup_teardown_temp_tables(cursor):
            cursor.copy_from(buffer, 'stations_reference_flow_temp', sep=",")
            cursor.execute(
                '''
                INSERT INTO stations_reference_flow (period_id, station_id, day_of_year, value)
                SELECT t.period_id, t.station_id, t.day_of_year, t.value
                FROM stations_reference_flow_temp t
                ON CONFLICT(period_id, station_id, day_of_year) DO UPDATE SET
                    value = EXCLUDED.value
                '''
            )