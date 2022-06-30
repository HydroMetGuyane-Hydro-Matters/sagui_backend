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
        for f in new_files:
            self.stdout.write("Publishing {}".format(os.path.basename(f)))
            self.netcdf_to_DB(f)

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
        last_updated_text = '20220627T1043'
        regex = '(.*)DATA_([0-9T]*)_'+last_updated_text+'([0-9]*)_([0-9]*)\\.nc'
        regex2 = '.*DATA_[0-9T]*_(\d{8}T\d{4})[0-9]*_[0-9]*\\.nc'
        all_filenames = glob.glob('/home/jean/dev/IRD/hyfaa-mgb-platform/hyfaa-scheduler/work_configurations/operational_guyane_gsmap/databases/forcing_onmesh_db/data_store/*.nc')
        new_files = [s for s in all_filenames if re.search(regex2, s).group(1) > '20220627T1005']
        return sorted(new_files)


    def netcdf_to_DB(self, file):
        tic = perf_counter()
        nc = Dataset(file, "r", format="netCDF4")
        nb_cells = nc.dimensions['n_meshes'].size
        rain_values = nc.variables['rain'][:].data
        # extract record date from filename
        regex = r'DATA_(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})'
        rec_date_re = re.search(regex, os.path.basename(file))
        # make it a proper date
        rec_date = datetime.fromisoformat("{}-{}-{}T{}:{}:00+00:00".format(rec_date_re.group(1),
                                                                                     rec_date_re.group(2),
                                                                                     rec_date_re.group(3),
                                                                                     rec_date_re.group(4),
                                                                                     rec_date_re.group(5)))
        records = [ RainFall(cell_id=i+1, date=rec_date, rain=rain_values[i]) for i in range(nb_cells)]
        RainFall.objects.bulk_update_or_create(records, ['rain'], match_field=['cell_id', 'date'])

        tac = perf_counter()
        self.stdout.write(self.style.SUCCESS('Processed in {} seconds'.format(tac - tic)))