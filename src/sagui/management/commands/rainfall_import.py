from datetime import datetime
import glob
from io import StringIO

from netCDF4 import Dataset
import numpy as np
import os
import pandas as pd
import psycopg2
import sqlite3
import psycopg2.extras as extras
from datetime import datetime
from time import perf_counter
import sys

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import connection, transaction

from sagui.utils import hyfaa as hyfaautils
from sagui.models import ImportState, RainFall

import re

def glob_re(pattern, strings):
    return filter(re.compile(pattern).match, strings)


class Command(BaseCommand):
    help = '''
    Rainfall netcdf files are an intermediate product of HYFAA-MGB algorithm but useful by themselves.
    Publish them to a pigeosolutions/hyfaa-postgis database. 
    
    First run publishes the whole serie of data (might take a long time). 
    Subsequent runs only perform an update (UPSERT) on data modified or added since the previous run.
    The connection parameters can be provided as argument or as an environment variable (DATABASE_URI)
    '''

    # Class-wide variables, that will be set using env var or command options
    rootpath         = None
    db_connect_url   = None
    db_schema        = None
    db_table        = None
    force_update     = None
    only_last_n_days = None
    commit_page_size = None
    tablename        = 'sagui_rainfall'
    last_updated_without_errors = None
    refresh_daysdelta: int = None

    def add_arguments(self, parser):
        parser.add_argument('-r', '--rootpath',
                            default=settings.SAGUI_SETTINGS.get('RAINFALL_NETCDF_FILES_PATH', ''),
                            help='Path to the sqlite DB listing the netcdf files (i.e. the path to forcing_onmesh_db/database_manager.sql)')
        parser.add_argument('-d', '--db_connect_url',
                            default=settings.SAGUI_SETTINGS.get('HYFAA_DATABASE_URI', None),
                            help='The connection URL for the DB. (Default: "postgresql://postgres:sagui@localhost:5432/sagui")')
        parser.add_argument('-s', '--schema',
                            default=settings.SAGUI_SETTINGS.get('HYFAA_DATABASE_SCHEMA', "guyane"),
                            help='The database schema to target')
        parser.add_argument('-t', '--table',
                            default="sagui_rainfall",
                            help='The target table')
        parser.add_argument('-f', '--force_update',
                            default=False,
                            action='store_true',
                            help='Force update on all values. By default, only data updated since last publish will be published')
        parser.add_argument('--only_last_n_days',
                            type=int,
                            default=None,
                            help='if set, only the only_last_n_days days will be published (useful for publishing only a sample of data. Default: None)')
        parser.add_argument('--commit_page_size',
                            type=int,
                            default=settings.SAGUI_SETTINGS.get('HYFAA_IMPORT_COMMIT_PAGE_SIZE', 1),
                            help='Commit the data into the DB every n different dates (default 1). Should run faster if set to 10 or 50')
        parser.add_argument('--refresh_daysdelta',
                            type=int,
                            default=3,
                            help='To always update data from the recent days, set this to the number of days from now that you want to refresh. Defaults to 3) ')

    def handle(self, *args, **kwargs):
        tic = perf_counter()

        self.rootpath = kwargs['rootpath']
        self.db_connect_url = kwargs.get('db_connect_url')
        self.db_schema = kwargs.get('schema')
        self.db_table = kwargs.get('table')
        self.force_update = kwargs.get('force_update')
        self.only_last_n_days = kwargs.get('only_last_n_days')
        self.commit_page_size = kwargs.get('commit_page_size')
        self.refresh_daysdelta = kwargs.get('refresh_daysdelta')

        self.stdout.write("Scanning folder {}".format(self.rootpath))
        new_files = self._get_files_list()
        # truncate the extraction to the last n days (useful when you are in a hurry)
        if self.only_last_n_days:
            new_files = new_files[-self.only_last_n_days:]

        if not new_files:
            self.stdout.write(self.style.SUCCESS("DB is up to date"))
            return

        if self.force_update:
            self.stdout.write("Emptying the table before loading the new data (--force_update was enabled)")
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute('TRUNCATE TABLE guyane.sagui_rainfall;')

        counter = 1
        errors = 0
        concatenated_df = pd.DataFrame()
        for f in new_files:
            self.stdout.write("Reading {}".format(os.path.basename(f[0])))
            df = self.netcdf_to_dataframe(f[0], f[1])
            concatenated_df = pd.concat([df, concatenated_df], ignore_index=True)
            if (counter % self.commit_page_size == 0) or (
                    f == new_files[-1]):  # last part means is last time element
                # try:
                #     # save dataframe to an in memory buffer, cf https://naysan.ca/2020/05/09/pandas-to-postgresql-using-psycopg2-bulk-insert-performance-benchmark/
                #     buffer = StringIO()
                #     concatenated_df.to_csv(buffer, header=False, index=False)
                #     buffer.seek(0)
                #
                #     # Execute the query
                #     with connection.cursor() as cursor:
                #         cursor.copy_from(buffer, 'sagui_rainfall', sep=",", columns = ('cell_id','date', 'rain'))
                #
                # except (Exception, psycopg2.DatabaseError) as error:
                #     print(error)
                #     errors += 1
                # finally:
                #     # clear the list of records
                #     concatenated_df = pd.DataFrame()
                # dataframe to DB
                e = self._publish_dataframe_to_db(concatenated_df)
                if not e:
                    self.stdout.write("Successfully published to DB")
                else:
                    self.stdout.write(self.style.ERROR(
                        "Encountered a DB error when publishing data to DB"))
                # count errors if there are
                errors += e

                concatenated_df = pd.DataFrame()

            counter +=1

        # Update the state table with the latest update date
        update_dates = [datetime.fromisoformat(f[1]+"+00:00") for f in new_files]
        # update_dates = [self._datetime_from_filename(f, regex) for f in new_files]
        last_update_date = max(update_dates)
        last_updated_without_errors = last_update_date if not errors else self.last_updated_without_errors
        tbl_state = ImportState.objects.update_or_create(tablename=self.tablename, defaults={
            "last_updated": last_update_date,
            "last_updated_jd": hyfaautils.datetime_to_julianday(last_update_date),
            "update_errors": errors,
            "last_updated_without_errors": last_updated_without_errors,
            "last_updated_without_errors_jd": hyfaautils.datetime_to_julianday(last_updated_without_errors),
        })

        tac = perf_counter()
        self.stdout.write(self.style.SUCCESS('Total processing time: {}'.format(tac - tic)))


    def _get_files_list(self):
        """
        List the files to import:
        - retrieve information from the state table, to determine the last import date. Unless self.force_update is True, then it will always import everything
        - load the files list from the sqlite db
        Returns: a list of tuples (file names, date)
        """
        tbl_state = ImportState.objects.filter(tablename__exact=self.tablename)

        last_updated_without_errors = datetime.fromisoformat('1970-01-01T00:00:00+00:00')
        self.last_updated_without_errors=last_updated_without_errors
        if self.force_update:
            # Don't filter, return everything. Force update on every date
            self.stdout.write("Forcing update on all the time values")
        elif tbl_state:
            tbl_state = tbl_state.first()
            last_updated_without_errors = tbl_state.last_updated_without_errors
        else:
            self.stdout.write("Importing for the first time: it will take some time (importing all dates in the file)")

        # List files that are more recent than that
        last_updated_text = last_updated_without_errors.strftime("%Y-%m-%d")
        # Execute a query over the sqlite DB
        conn = sqlite3.connect(self.rootpath)
        cur = conn.cursor()
        q = f'''
            SELECT file_path, data_type, date_data, date_added_to_db, date_created, product_type, file_status, grid_status
            FROM (
              SELECT *,
                ROW_NUMBER() OVER (
                  PARTITION BY DATE(date_data)
                  ORDER BY CASE product_type
                    WHEN 'analysis'       THEN 1
                    WHEN 'analysis-early' THEN 2
                  END
                ) AS rn
              FROM FILEINFO
              WHERE product_type IN ('analysis', 'analysis-early') AND
                  DATE(date_data) > DATE('{last_updated_text}', '-{self.refresh_daysdelta} day')
            )
            WHERE rn = 1
            ORDER BY DATE(date_data);
        '''
        cur.execute(q)
        new_files=cur.fetchall()
        conn.close()
        filtered_new_files = [(f[0], f[2]) for f in new_files]
        return filtered_new_files

    def netcdf_to_dataframe(self, file , date):
        """
        Read a netcdf file and return a pandas dataframe
        :param file: name of the file to read
        :param date: date corresponding to the file
        :return:
        """
        filepath = os.path.join(os.path.dirname(self.rootpath), "data_store", file)
        nc = Dataset(filepath, "r", format="netCDF4")
        nb_cells = nc.dimensions['n_meshes'].size
        rain_values = nc.variables['rain'][:].data

        rec_date = datetime.fromisoformat(date)

        columns_dict = {
            'cell_id': np.arange(start=1, stop=nb_cells + 1, dtype='i2'),
            'date': np.full(nb_cells, rec_date),
            'rain': nc.variables['rain'][:].data,
        }
        df = pd.DataFrame.from_dict(columns_dict)
        return df


    def _publish_dataframe_to_db(self, df):
        """
        Publish the provided Pandas DataFrame into the DB.
        Returns: - nb of errors if there were (0 if everything went well)
        Params:
          * df: pandas dataframe to publish
          * tblname
        """
        try:
            # Create a list of tuples from the dataframe values
            tuples = [tuple(x) for x in df.to_numpy()]
            # tuples = df.to_records(index=False).tolist() # seems faster but breaks the datetimes
            # Comma-separated dataframe columns
            cols = ','.join(list(df.columns))

            # Run an upsert command (on conflict etc)
            # Considers that the pkey is composed of the 2 first fields:
            updatable_cols = list(df.columns)[2:]


            # Write the update statement (internal part). EXCLUDED is a PG internal table contained rejected rows from the insert
            # see https://www.postgresql.org/docs/10/sql-insert.html#SQL-ON-CONFLICT
            externals = lambda n: "{n}=EXCLUDED.{n}".format(n=n)
            update_stmt = ','.join(["%s" % (externals(name)) for name in updatable_cols])
            query = "INSERT INTO {schema}.{table}({cols}) VALUES %s ON CONFLICT ON CONSTRAINT  rainfall_unique_cellid_day DO UPDATE SET {updt_stmt};".format(
                schema=self.db_schema, table=self.db_table, cols=cols, updt_stmt=update_stmt)

            # Execute the query
            with connection.cursor() as cursor:
                extras.execute_values(cursor, query, tuples)
            return 0
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
            return 1

    @staticmethod
    def _datetime_from_filename(filename, regex):
        d_re = re.search(regex, os.path.basename(filename))
        # make it a proper date
        d = datetime.fromisoformat("{}-{}-{}T{}:{}:00+00:00".format(d_re.group(1),
                                                                       d_re.group(2),
                                                                       d_re.group(3),
                                                                       d_re.group(4),
                                                                       d_re.group(5)))
        return d