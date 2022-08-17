from netCDF4 import Dataset
import numpy as np
import os
import pandas as pd
import psycopg2
import psycopg2.extras as extras
from time import perf_counter
import sys

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import connection

from sagui import utils
from sagui import models


class Command(BaseCommand):
    help = '''
    Parse a bunch of netCDF4 files produced with data from HYFAA-MGB algorithm. 
    Publish it to a pigeosolutions/hyfaa-postgis database. 
    
    First run publishes the whole serie of data (might take a long time). 
    Subsequent runs only perform an update (UPSERT) on data modified or added since the previous run.
    The connection parameters can be provided as argument or as an environment variable (DATABASE_URI)
    '''

    # Class-wide variables, that will be set using env var or command options
    rootpath         = None
    db_connect_url   = None
    db_schema        = None
    force_update     = None
    only_last_n_days = None
    max_ordem        = None
    commit_page_size = None
    config           = None

    def add_arguments(self, parser):
        parser.add_argument('-r', '--rootpath',
                            default=settings.SAGUI_SETTINGS.get('HYFAA_IMPORT_NETCDF_ROOT_PATH', ''),
                            help='NetCDF4 files root path (i.e. the path of the folder containing the assimilated_solution_databases, mgbstandard_solution_databases folders)')
        parser.add_argument('-d', '--db_connect_url',
                            default=settings.SAGUI_SETTINGS.get('HYFAA_DATABASE_URI', None),
                            help='The connection URL for the DB. (Default: "postgresql://postgres:sagui@localhost:5432/sagui")')
        parser.add_argument('-s', '--schema',
                            default=settings.SAGUI_SETTINGS.get('HYFAA_DATABASE_SCHEMA', 'hyfaa'),
                            help='DB schema (Default: "hyfaa")')
        parser.add_argument('-f', '--force_update',
                            default=False,
                            action='store_true',
                            help='Force update on all values. By default, only data updated since last publish will be published')
        parser.add_argument('--only_last_n_days',
                            type=int,
                            default=None,
                            help='if set, only the only_last_n_days days will be published (useful for publishing only a sample of data. Default: None)')
        parser.add_argument('--max_ordem',
                            type=int,
                            default=None,
                            help='max ordem value for the cells to import: needs the ')
        parser.add_argument('--commit_page_size',
                            type=int,
                            default=settings.SAGUI_SETTINGS.get('HYFAA_IMPORT_COMMIT_PAGE_SIZE', 1),
                            help='Commit the data into the DB every n different dates (default 1). Should run faster if set to 10 or 50')

    def handle(self, *args, **kwargs):
        tic = perf_counter()

        self.rootpath = kwargs['rootpath']
        self.db_connect_url = kwargs.get('db_connect_url')
        self.db_schema = kwargs.get('schema')
        self.force_update = kwargs.get('force_update')
        self.only_last_n_days = kwargs.get('only_last_n_days')
        self.max_ordem = kwargs.get('max_ordem')
        self.commit_page_size = kwargs.get('commit_page_size')
        self.config = settings.SAGUI_SETTINGS.get('HYFAA_IMPORT_STRUCTURE_CONFIG')

        if not self.config:
            self.stdout.write(self.style.ERROR("Could not load import config data (missing SAGUI_SETTINGS.HYFAA_IMPORT_STRUCTURE_CONFIG)"))
            sys.exit(1)


        for ds in self.config['sources']:
            self.stdout.write('#######################################################')
            self.stdout.write('Processing data for serie {}'.format(ds['name']))
            self.stdout.write('#######################################################')
            nc_path = os.path.join(self.rootpath, ds['file'])
            # logging.info('Publishing {} data from {} to DB {} table'.format(ds['name'], nc_path, ds['tablename']))
            # beware, this is a bit acrobatic, I'm altering here the path in the configuration object
            ds['file'] = nc_path
            self.publish_nc(ds)

        tac = perf_counter()
        self.stdout.write(self.style.SUCCESS('Total processing time: {} s'.format( round(tac - tic), 2 )))


    def _extract_data_to_dataframe_at_time(self, nc, ds, t):
        """
        Retrieves data from netcdf variables, for the given time value. Organizes it into a Pandas dataframe with proper
        layout, to optimize publication into PostgreSQL DB
        Params:
          * nc: netcdf4.Dataset input file
          * ds: dataserie definition (one element of global script_config['sources'] list)
          * t: time to look for
        """
        self.stdout.write("Preparing data for day {} (index {})".format(t[1], t[0]))
        itime = t[0]
        nb_cells = nc.dimensions['n_cells'].size
        # We will group the netcdf variables as columns of a 2D matrix (the pandas dataframe)
        # Common columns
        columns_dict = {
            'cell_id': np.arange(start=1, stop=nb_cells + 1, dtype='i2'),
            'date': utils.vfunc_jd_to_dt(np.full((nb_cells), nc.variables['time'][itime])),
            'update_time': utils.vfunc_jd_to_dt(np.full((nb_cells), nc.variables['time_added_to_hydb'][itime])),
            'is_analysis': np.full((nb_cells), nc.variables['is_analysis'][itime], dtype='?')
        }
        # dynamic columns: depend on the dataserie considered
        for j in ds['nc_data_vars']:
            columns_dict[self.config['short_names'][j]] = nc.variables[j][itime, :].data

        df = pd.DataFrame.from_dict(columns_dict)

        # force cell_id type to smallint
        df = df.astype({
            'cell_id': 'int16',
            'is_analysis': 'boolean'
        })

        # self.stdout.write(df)
        return df


    def _filter_dataframe(self, dataframe):
        """
        Filters the dataframe based on a provided ordem value. This value is checked on the
        minibasins_data table to get the list of 'mini' values that pass it (must be >= max_ordem)
        max_ordem is either defined as a parameter to this command, or taken from the sagui_saguiconfig table
        :param dataframe:
        :return: same dataframe, filtered
        """
        if not self.max_ordem:
            # Filter out data based on the Import max ordem value configured in DB
            conf = models.SaguiConfig.objects.order_by('id').last()
            if conf:
                self.max_ordem = conf.max_ordem
        if self.max_ordem:
            mini_recs = models.MinibasinsData.objects.filter(ordem__gte=self.max_ordem).values_list('mini', flat=True)
            mini_list = list(mini_recs)
            dataframe.query('cell_id in @mini_list', inplace=True)
        return dataframe


    def _publish_dataframe_to_db(self, df, ds):
        """
        Publish the provided Pandas DataFrame into the DB.
        Returns: - nb of errors if there were (0 if everything went well)
        Params:
          * df: pandas dataframe to publish
          * ds: dataserie definition (one element of global script_config['sources'] list)
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
            query = "INSERT INTO {schema}.{table}({cols}) VALUES %s ON CONFLICT ON CONSTRAINT  {table}_unique_cellid_day DO UPDATE SET {updt_stmt};".format(
                schema=self.db_schema, table=ds['tablename'], cols=cols, updt_stmt=update_stmt)

            # Execute the query
            with connection.cursor() as cursor:
                extras.execute_values(cursor, query, tuples)
            return 0
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
            return 1

    def publish_nc(self, ds):
        """
        Publish a netcdf4 dataset.
        First extracts the state information from the database, to publish/.update only the records that need it
        Then publishes them using an UPSERT command.
        Finally updates the `state` table
        Params:
          * ds: dataserie definition (one element of global self.config['sources']  list, see above)
        """
        nc = Dataset(ds['file'], "r", format="netCDF4")
        # Check when was the last data publication (only publish data that need to be)
        update_times, last_updated_without_errors_jd = self._retrieve_times_to_update(nc, ds['tablename'])

        # truncate the extraction to the last n days (useful when you are in a hurry)
        if self.only_last_n_days:
            update_times = update_times[-self.only_last_n_days:]

        if not update_times:
            self.stdout.write(self.style.SUCCESS("DB is up to date"))
            return

        # # Iterate and publish all recent times
        errors = 0
        # Initialize transitional dataframe and counter. This is a mechanims for paginating DB commits (not commit every
        # different time, which is very slow
        concatenated_df = pd.DataFrame()
        counter = 1
        for t in update_times:
            tic = perf_counter()
            # netcdf to dataframe
            df = self._extract_data_to_dataframe_at_time(nc, ds, t)
            concatenated_df = pd.concat([df, concatenated_df])

            if (counter % self.commit_page_size == 0) or (
                    t[0] == update_times[-1][0]):  # last part means is last time element
                # dataframe to DB
                e = self._publish_dataframe_to_db(concatenated_df, ds)
                if not e:
                    self.stdout.write("Published data for time {} (index {}, greg. time {})".format(t[1], t[0],
                                                                                               utils.julianday_to_datetime(
                                                                                                   t[1])))
                else:
                    self.stdout.write(self.style.ERROR(
                        "Encountered a DB error when publishing data for time {} ({}). Please watch your logs".format(
                            t[0], t[1])))
                # count errors if there are
                errors += e

                concatenated_df = pd.DataFrame()
            counter += 1

            tac = perf_counter()
            self.stdout.write("processing time: {} s".format( round(tac - tic), 2 ))

        last_published_day_jd = max(list(zip(*update_times))[1])
        if not errors:
            # increment last update time without error
            last_updated_without_errors_jd = max(list(zip(*update_times))[2])
        # update state table
        # _update_state(ds, errors, last_published_day_jd, last_updated_without_errors_jd)
        tbl_state = models.ImportState.objects.update_or_create(tablename=ds['tablename'], defaults={
            "last_updated": utils.julianday_to_datetime(last_published_day_jd),
            "last_updated_jd": last_published_day_jd,
            "update_errors": errors,
            "last_updated_without_errors": utils.julianday_to_datetime(last_updated_without_errors_jd),
            "last_updated_without_errors_jd": last_updated_without_errors_jd,
        })
        # tbl_state.save() # should not be necessary



    def _retrieve_times_to_update(self, nc, tablename):
        """
        Extract the list of times where the data have been updated (unless FORCE_UPDATE is True, in which case it will return
        all the time values
        Returns: a 3-tuple list: (time index, time value, time at which the data --for this time-frame-- was last updated)
        """
        update_times = None
        last_published_day = 0
        last_updated_without_errors_jd = 0

        # Build a list of all indices-time value (Julian Day)
        times_array = list(zip(
            np.arange(start=0, stop=nc.dimensions['n_time'].size, dtype='i4'),
            nc.variables['time'][:],
            nc.variables['time_added_to_hydb'][:]
        ))

        if self.force_update:
            # Don't filter, return everything. Force update on every date
            self.stdout.write("Forcing update on all the time values")
            return times_array, 0

        tbl_state = models.ImportState.objects.filter(tablename__exact=tablename)

        if not tbl_state:
            # Don't filter, return everything. Force update on every date
            self.stdout.write("Importing for the first time: it will take some time (importing all dates in the file)")
            return times_array, 0

        tbl_state = tbl_state.first()
        last_published_day = tbl_state.last_updated_jd
        last_updated_without_errors_jd = tbl_state.last_updated_without_errors_jd

        # Filter to only the times posterior to last update (fetching the time the data was added
        # -> handles updates on old data if needs be
        update_times = list(filter(lambda t: t[2] > last_updated_without_errors_jd, times_array))

        return update_times, last_updated_without_errors_jd

