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
        CREATE TEMPORARY TABLE stations_reference_flow_temp AS SELECT id, period_id, station_id, day_of_year, flow FROM stations_reference_flow LIMIT 0;
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
    Expected content for the csv file is expected to be produced by the reference_data_from_MGB_run.py script
    (key-value output) and comply to the following structure:
        ref_period,mini,day_of_year,flow
        1980-1990,3467,1,-59.0
        1980-1990,3467,2,-61.3
        1980-1990,3467,3,-61.5
        1980-1990,3467,4,-60.9
        1980-1990,3467,5,-59.5
        ...
    ref_period should already exist in the DB table stations_reference_flow_period
    :param csv_file: can be any input accepted by pandas read_csv function: file path, stream, ByteIO
    :return:
    """
    # Get list of available periods (declared in UI/DB)
    periods = models.StationsReferenceFlowPeriod.objects.all().values()
    period_names = [p['period'] for p in periods]

    # Get list of station ids (only allow to try to import those)
    stations = models.Stations.objects.values('id', 'name', 'minibasin').order_by('id')
    df = pd.read_csv(csv_file, sep=',', dtype={
        'ref_period': "string",
        'mini': 'int16',
        'day_of_year': 'int16',
        'flow': 'float32',
    })

    # filter out periods that are not valid (not declared)
    df.query("ref_period in " + str(period_names), inplace=True)

    # Round and convert flow values to int
    df['flow'] = df['flow'].apply(np.int64)

    # Replace the target_periods column par a column with period_id referring to the periods table
    p = {i['period']: i['id'] for i in periods}
    df['ref_period'] = df['ref_period'].map(p)

    # filter out stations that do not exist in the DB
    df.query("mini in " + str([s['minibasin'] for s in stations]), inplace=True)

    # Replace the mini field by the station id
    p = {i['minibasin']: i['id'] for i in stations}
    df['mini'] = df['mini'].map(p)
    df.rename({'ref_period': 'period_id', 'mini': 'station_id'}, axis=1, inplace=True)

    # Save to CSV file
    df.to_csv('/tmp/df2.csv', index=False)

    # save dataframe to an in memory buffer, cf https://naysan.ca/2020/05/09/pandas-to-postgresql-using-psycopg2-bulk-insert-performance-benchmark/
    buffer = StringIO()
    df.to_csv(buffer, columns=['period_id', 'station_id', 'day_of_year', 'flow'], header=False, index=True)
    buffer.seek(0)
    # Write the data into the DB using copy from and an upsert query
    # Inspired from https://www.thebookofjoel.com/django-fast-bulk-upsert
    with connection.cursor() as cursor:
        with setup_teardown_temp_tables(cursor):
            cursor.copy_from(buffer, 'stations_reference_flow_temp', sep=",")
            cursor.execute(
                '''
                INSERT INTO stations_reference_flow (period_id, station_id, day_of_year, flow)
                SELECT t.period_id, t.station_id, t.day_of_year, t.flow
                FROM stations_reference_flow_temp t
                ON CONFLICT(period_id, station_id, day_of_year) DO UPDATE SET
                    flow = EXCLUDED.flow
                '''
            )
