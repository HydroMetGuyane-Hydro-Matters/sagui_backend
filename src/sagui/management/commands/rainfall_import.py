from datetime import datetime
import glob
from netCDF4 import Dataset
import numpy as np
import os
import pandas as pd
import psycopg2
import psycopg2.extras as extras
from datetime import datetime
from time import perf_counter
import sys

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import connection

from sagui import utils
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
    force_update     = None
    only_last_n_days = None
    commit_page_size = None
    tablename        = 'sagui_rainfall'
    last_updated_without_errors = None

    def add_arguments(self, parser):
        parser.add_argument('-r', '--rootpath',
                            default=settings.SAGUI_SETTINGS.get('RAINFALL_NETCDF_FILES_PATH', ''),
                            help='NetCDF4 files root path (i.e. the path of the folder forcing_onmesh_db/data_store/)')
        parser.add_argument('-d', '--db_connect_url',
                            default=settings.SAGUI_SETTINGS.get('HYFAA_DATABASE_URI', None),
                            help='The connection URL for the DB. (Default: "postgresql://postgres:sagui@localhost:5432/sagui")')
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

    def handle(self, *args, **kwargs):
        tic = perf_counter()

        self.rootpath = kwargs['rootpath']
        self.db_connect_url = kwargs.get('db_connect_url')
        self.force_update = kwargs.get('force_update')
        self.only_last_n_days = kwargs.get('only_last_n_days')
        self.commit_page_size = kwargs.get('commit_page_size')

        new_files = self._get_files_list()
        # truncate the extraction to the last n days (useful when you are in a hurry)
        if self.only_last_n_days:
            new_files = new_files[-self.only_last_n_days:]

        if not new_files:
            self.stdout.write(self.style.SUCCESS("DB is up to date"))
            return

        counter = 1
        errors = 0
        concatenated_df = pd.DataFrame()
        for f in new_files:
            self.stdout.write("Reading {}".format(os.path.basename(f)))
            df = self.netcdf_to_dataframe(f)
            concatenated_df = pd.concat([df, concatenated_df])
            if (counter % self.commit_page_size == 0) or (
                    f == new_files[-1]):  # last part means is last time element
                try:
                    records = [ RainFall(cell_id=x[0], date=x[1], rain=x[2]) for x in df.to_numpy()]
                    self.stdout.write("Writing to DB")
                    RainFall.objects.bulk_update_or_create(records, ['rain'], match_field=['cell_id', 'date'])
                except (Exception, psycopg2.DatabaseError) as error:
                    print(error)
                    errors += 1

            counter +=1

        # Update the state table
        # Get the lastest update date from the filenames
        regex = r'DATA_[0-9T]*_(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})'
        update_dates = [self._datetime_from_filename(f, regex) for f in new_files]
        last_update_date = max(update_dates)
        last_updated_without_errors = last_update_date if not errors else self.last_updated_without_errors
        tbl_state = ImportState.objects.update_or_create(tablename=self.tablename, defaults={
            "last_updated": last_update_date,
            "last_updated_jd": utils.datetime_to_julianday(last_update_date),
            "update_errors": errors,
            "last_updated_without_errors": last_updated_without_errors,
            "last_updated_without_errors_jd": utils.datetime_to_julianday(last_updated_without_errors),
        })

        tac = perf_counter()
        self.stdout.write(self.style.SUCCESS('Total processing time: {}'.format(tac - tic)))


    def _get_files_list(self):
        """
        List the files to import:
        - retrieve information from the state table, to determine the last import date
        - compare it with the folder's content (note: it's not using the sqlitedb)
        Returns: a list of file names (strings)
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
        last_updated_text = last_updated_without_errors.strftime("%Y%m%dT%H%M")
        # regex = '(.*)DATA_([0-9T]*)_'+last_updated_text+'([0-9]*)_([0-9]*)\\.nc'
        regex2 = '.*DATA_[0-9T]*_(\d{8}T\d{4})[0-9]*_[0-9]*\\.nc'
        all_filenames = glob.glob('/home/jean/dev/IRD/hyfaa-mgb-platform/hyfaa-scheduler/work_configurations/operational_guyane_gsmap/databases/forcing_onmesh_db/data_store/*.nc')
        new_files = sorted([s for s in all_filenames if re.search(regex2, s).group(1) > last_updated_text])
        if not new_files:
            return None

        # Some days might have been downloaded several times with different datestamps (last part of the name)
        # => we only need the most recent one
        filtered_new_files = []
        for i in range(len(new_files)-1):
            if os.path.basename(new_files[i])[:18] != os.path.basename(new_files[i+1])[:18] :
                filtered_new_files.append(new_files[i])
        filtered_new_files.append(new_files[-1]) # last one is always the most recent, since it is a sorted list
        return filtered_new_files

    def netcdf_to_dataframe(self, file):
        nc = Dataset(file, "r", format="netCDF4")
        nb_cells = nc.dimensions['n_meshes'].size
        rain_values = nc.variables['rain'][:].data

        # extract record date from filename
        regex = r'DATA_(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})'
        rec_date = self._datetime_from_filename(file, regex)

        columns_dict = {
            'cell_id': np.arange(start=1, stop=nb_cells + 1, dtype='i2'),
            'date': np.full(nb_cells, rec_date),
            'rain': nc.variables['rain'][:].data,
        }
        df = pd.DataFrame.from_dict(columns_dict)
        return df

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