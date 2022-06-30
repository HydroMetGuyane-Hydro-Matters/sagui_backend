from django.db import models
from django.contrib.gis.db import models as geomodels
from bulk_update_or_create import BulkUpdateOrCreateQuerySet

# HYFAA Data models -> store them in hyfaa schema ?

class AbstractHyfaaData(models.Model):
    cell_id = models.SmallIntegerField("Minibasin ID", null=False, unique_for_date="date",
                help_text='Cell identifier. Called ''cell'' in HYFAA netcdf file, field ''MINI'' in geospatial file')
    date = models.DateField("Date", null=False,
                help_text='Date for the values')
    elevation_mean = models.FloatField(null=True, help_text='Water elevation in m. Mean value')
    flow_mean = models.FloatField(null=True, help_text='Stream flow. Mean value')
    update_time = models.DateTimeField(null=True, help_text='Time of last update')
    is_analysis = models.BooleanField(null=True, help_text='Boolean. Whether the value comes from analysis or control series')

    class Meta:
        abstract = True


    def __str__(self):
        return 'cell {} | {} | {}'.format(self.cell_id, self.date, self.flow_mean)


class DataMgbStandard(AbstractHyfaaData):
    # Support bulk_update_or_create actions, see https://pypi.org/project/django-bulk-update-or-create/
    objects = BulkUpdateOrCreateQuerySet.as_manager()

    flow_expected = models.FloatField(null=True, help_text='Expected value. Calculated using a floating median, over the flow_median values taken on the day surrounding the current day (+ or - 10 days around), during the previous years')
    flow_anomaly = models.FloatField(null=True, help_text='Represents the anomaly compared to expected data. Formula is 100 * (anomaly - expected) / expected')

    class Meta:
        db_table = 'data_mgbstandard' # will be in hyfaa, but not managed => found through the SEARCH_PATH
        managed = False
        verbose_name = 'MGB hydrological data, calculated using HYFAA scheduler, without assimilation'
        constraints = [
            models.UniqueConstraint(fields=["cell_id", "date"], name="data_mgbstandard_unique_cellid_day"),
        ]
        indexes = [
            models.Index(fields=['-date']),
            models.Index(fields=['cell_id', '-date']),
        ]


class DataForecast(AbstractHyfaaData):
    # Support bulk_update_or_create actions, see https://pypi.org/project/django-bulk-update-or-create/
    objects = BulkUpdateOrCreateQuerySet.as_manager()

    elevation_median = models.FloatField(null=True, help_text='Water elevation in m. Median value')
    elevation_stddev = models.FloatField(null=True, help_text='Water elevation in m. Standard deviation')
    elevation_mad = models.FloatField(null=True, help_text='Water elevation in m. Median absolute deviation')
    flow_median = models.FloatField(null=True, help_text='Stream flow. Median value')
    flow_stddev = models.FloatField(null=True, help_text='Stream flow. Standard deviation')
    flow_mad = models.FloatField(null=True, help_text='Stream flow. Median absolute  deviation')

    class Meta:
        db_table = 'data_forecast' # will be in hyfaa, but not managed => found through the SEARCH_PATH
        managed = False
        verbose_name = 'Forecast MGB hydrological data, calculated using HYFAA scheduler, with assimilation'
        constraints = [
            models.UniqueConstraint(fields=["cell_id", "date"], name="data_forecast_unique_cellid_day"),
        ]
        indexes = [
            models.Index(fields=['-date']),
            models.Index(fields=['cell_id', '-date']),
        ]


class DataAssimilated(AbstractHyfaaData):
    # Support bulk_update_or_create actions, see https://pypi.org/project/django-bulk-update-or-create/
    objects = BulkUpdateOrCreateQuerySet.as_manager()

    # Same as Forecast
    elevation_median = models.FloatField(null=True, help_text='Water elevation in m. Median value')
    elevation_stddev = models.FloatField(null=True, help_text='Water elevation in m. Standard deviation')
    elevation_mad = models.FloatField(null=True, help_text='Water elevation in m. Median absolute deviation')
    flow_median = models.FloatField(null=True, help_text='Stream flow. Median value')
    flow_stddev = models.FloatField(null=True, help_text='Stream flow. Standard deviation')
    flow_mad = models.FloatField(null=True, help_text='Stream flow. Median absolute  deviation')

    # Same as MgbStandard
    flow_expected = models.FloatField(null=True, help_text='Expected value. Calculated using a floating median, over the flow_median values taken on the day surrounding the current day (+ or - 10 days around), during the previous years')
    flow_anomaly = models.FloatField(null=True, help_text='Represents the anomaly compared to expected data. Formula is 100 * (anomaly - expected) / expected')

    class Meta:
        db_table = 'data_assimilated' # will be in hyfaa, but not managed => found through the SEARCH_PATH
        managed = False
        verbose_name = 'MGB hydrological data, calculated using HYFAA scheduler, with assimilation'
        constraints = [
            models.UniqueConstraint(fields=["cell_id", "date"], name="data_assimilated_unique_cellid_day"),
        ]
        indexes = [
            models.Index(fields=['-date']),
            models.Index(fields=['cell_id', '-date']),
        ]


# Base geospatial data
class DrainageInclusionMask(geomodels.Model):
    name = models.CharField(max_length=50, null=True)
    mask = geomodels.PolygonField()

    class Meta:
        db_table = 'geospatial_inclusion_mask'
        # managed = False
        verbose_name = 'Inclusion Mask. Only data included in this mask polygons will be displayed. Overrides hyfaa exclusion mask'
        indexes = [
            models.Index(fields=['mask']),
        ]

    def __str__(self):
        return '{}'.format(self.name)


class Drainage(geomodels.Model):
    mini =  models.SmallIntegerField("Minibasin ID", null=False, primary_key=True,
                help_text='Minibasin identifier. Called ''cell'' in HYFAA netcdf file, field ''mini'' in geospatial file')
    geom = geomodels.LineStringField()

    class Meta:
        db_table = 'drainage'  # will be in hyfaa, but not managed => found through the SEARCH_PATH
        managed = False
        verbose_name = 'Drainage data (mini-sections of river/drainage) by minibasin'
        indexes = [
            models.Index(fields=['geom']),
        ]
        ordering = ['mini']

    def __str__(self):
        return 'Mini {}'.format(self.mini)


# SAGUI-specific models
class RainFall(models.Model):
    # Support bulk_update_or_create actions, see https://pypi.org/project/django-bulk-update-or-create/
    objects = BulkUpdateOrCreateQuerySet.as_manager()

    cell_id = models.SmallIntegerField("Minibasin ID", null=False, unique_for_date="date",
                help_text='Cell identifier. Called ''cell'' in HYFAA netcdf file, field ''MINI'' in geospatial file')
    date = models.DateField("Date", null=False,
                help_text='Date for the values')
    rain = models.FloatField("Rain fall")

    class Meta:
        verbose_name = 'Rainfall data (GSMap for now)'
        constraints = [
            models.UniqueConstraint(fields=["cell_id", "date"], name="rainfall_unique_cellid_day"),
        ]
        indexes = [
            models.Index(fields=['-date']),
            models.Index(fields=['cell_id', '-date']),
        ]
        ordering = ['-date']


class Stations(geomodels.Model):
    name = models.CharField(max_length=50, null=False)
    river = models.CharField(max_length=50, null=True, blank=True)
    minibasin = models.ForeignKey(Drainage, to_field='mini', on_delete=models.CASCADE)
    threshold_drought = models.FloatField("Drought threshold", default=-9999,
        help_text='in m3/s; when no threshold is defined, value is -9999; The values are the low limit of the category')
    threshold_flood_low = models.FloatField("Flood low threshold", default=-9999,
        help_text='in m3/s; when no threshold is defined, value is -9999; The values are the low limit of the category')
    threshold_flood_mid = models.FloatField("Flood mid threshold", default=-9999,
        help_text='in m3/s; when no threshold is defined, value is -9999; The values are the low limit of the category')
    threshold_flood_high = models.FloatField("Flood high threshold", default=-9999,
        help_text='in m3/s; when no threshold is defined, value is -9999; The values are the low limit of the category')
    geom = geomodels.PointField(null=True)

    class Meta:
        verbose_name = 'Virtual station'
        db_table = 'stations' # will be in hyfaa, but not managed => found through the SEARCH_PATH
        managed = False
        constraints = [
            models.UniqueConstraint(fields=["name"], name="stations_name_unique"),
        ]
        ordering = ['name']

    def __str__(self):
        return '{} ( riv. {} / {})'.format(self.name, self.river, self.minibasin)


class ImportState(models.Model):
    tablename = models.CharField(max_length=20, null=False, primary_key=True)
    last_updated = models.DateTimeField("Last Updated", default='1950-01-01T00:00:00.000Z00',
            help_text='Datetime of last update from the netcdf data file')
    last_updated_jd = models.FloatField('Last updated in Julian days', default=0,
            help_text='Datetime of last update from the netcdf data file. In CNES Julian days (0 is 01/01/1950)')
    update_errors = models.SmallIntegerField("Update errors", default=0,
            help_text='Nb of errors during update')
    last_updated_without_errors = models.DateTimeField("Last Updated", default='1950-01-01T00:00:00.000Z00',
            help_text='Datetime of last update from the netcdf data file')
    last_updated_without_errors_jd = models.FloatField('Last updated in Julian days', default=0,
            help_text='Datetime of last update from the netcdf data file. In CNES Julian days (0 is 01/01/1950)')

    class Meta:
        verbose_name = 'Information about the current state of the DB'
        ordering = ['tablename']

    def __str__(self):
        return '{}: {} ({} JD), {} errors'.format(self.tablename, self.last_updated, self.last_updated_jd, self.update_errors)
