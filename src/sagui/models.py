from django.db import models
from django.contrib.gis.db import models as geomodels

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
    flow_expected = models.FloatField(null=True, help_text='Expected value. Calculated using a floating median, over the flow_median values taken on the day surrounding the current day (+ or - 10 days around), during the previous years')
    flow_anomaly = models.FloatField(null=True, help_text='Represents the anomaly compared to expected data. Formula is 100 * (anomaly - expected) / expected')

    class Meta:
        db_table = 'hyfaa_data_mgbstandard'
        # managed = False
        verbose_name = 'MGB hydrological data, calculated using HYFAA scheduler, without assimilation'
        constraints = [
            models.UniqueConstraint(fields=["cell_id", "date"], name="hyfaa_data_mgbstandard_unique_cellid_day"),
        ]
        indexes = [
            models.Index(fields=['-date']),
            models.Index(fields=['cell_id', '-date']),
        ]


class DataForecast(AbstractHyfaaData):
    elevation_median = models.FloatField(null=True, help_text='Water elevation in m. Median value')
    elevation_stddev = models.FloatField(null=True, help_text='Water elevation in m. Standard deviation')
    elevation_mad = models.FloatField(null=True, help_text='Water elevation in m. Median absolute deviation')
    flow_median = models.FloatField(null=True, help_text='Stream flow. Median value')
    flow_stddev = models.FloatField(null=True, help_text='Stream flow. Standard deviation')
    flow_mad = models.FloatField(null=True, help_text='Stream flow. Median absolute  deviation')

    # Same as MgbStandard
    flow_expected = models.FloatField(null=True, help_text='Expected value. Calculated using a floating median, over the flow_median values taken on the day surrounding the current day (+ or - 10 days around), during the previous years. Computed from data taken in assimilated table')
    flow_anomaly = models.FloatField(null=True, help_text='Represents the anomaly compared to expected data. Formula is 100 * (anomaly - expected) / expected')


    class Meta:
        db_table = 'hyfaa_data_forecast'
        # managed = False
        verbose_name = 'Forecast MGB hydrological data, calculated using HYFAA scheduler, with assimilation'
        constraints = [
            models.UniqueConstraint(fields=["cell_id", "date"], name="hyfaa_data_forecast_unique_cellid_day"),
        ]
        indexes = [
            models.Index(fields=['-date']),
            models.Index(fields=['cell_id', '-date']),
        ]


class DataAssimilated(AbstractHyfaaData):
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
        db_table = 'hyfaa_data_assimilated'
        # managed = False
        verbose_name = 'MGB hydrological data, calculated using HYFAA scheduler, with assimilation'
        constraints = [
            models.UniqueConstraint(fields=["cell_id", "date"], name="hyfaa_data_assimilated_unique_cellid_day"),
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
        db_table = 'hyfaa_geo_inclusion_mask'
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
        db_table = 'hyfaa_drainage'
        # managed = False
        verbose_name = 'Drainage data (mini-sections of river/drainage) by minibasin'
        indexes = [
            models.Index(fields=['geom']),
            models.Index(fields=['mini']),
        ]
        constraints = [
            models.UniqueConstraint(fields=["mini"], name="drainage_unique_mini"),
        ]
        ordering = ['mini']

    def __str__(self):
        return 'Mini {}'.format(self.mini)


class Catchments(geomodels.Model):
    mini =  models.SmallIntegerField("Minibasin ID", null=False,
                help_text='Minibasin identifier. Called ''cell'' in HYFAA netcdf file, field ''mini'' in geospatial file')
    sub = models.SmallIntegerField("Subbasin ID", null=False,
                help_text='Subbasin identifier. Subbasin are the level above minibasins')
    geom = geomodels.PolygonField()

    class Meta:
        db_table = 'hyfaa_catchments'
        # managed = False
        verbose_name = 'Drainage data (mini-sections of river/drainage) by minibasin'
        indexes = [
            models.Index(fields=['geom']),
            models.Index(fields=['mini']),
        ]
        constraints = [
            models.UniqueConstraint(fields=["mini"], name="catchments_unique_mini"),
        ]
        ordering = ['mini']

    def __str__(self):
        return 'Mini {}'.format(self.mini)


class MinibasinsData(models.Model):
    mini =  models.SmallIntegerField("Minibasin ID", null=False, primary_key=True,
                help_text='Minibasin identifier. Called ''cell'' in HYFAA netcdf file, field ''mini'' in geospatial file')
    ordem = models.SmallIntegerField('Ordem', help_text='Defines the importance of the minibasin. The higher the more important')
    sub = models.SmallIntegerField('Sub', help_text='Id of parent sub-basin')
    width = models.FloatField('Width')
    depth = models.FloatField('Depth')

    class Meta:
        db_table = 'hyfaa_minibasins_data'
        #managed = False
        verbose_name = 'Data associated to minibasins (for join with drainage or catchment data). Non-geo table as it is now'
        indexes = [
            models.Index(fields=['mini']),
            models.Index(fields=['ordem', 'mini']),
            models.Index(fields=['sub']),
        ]
        constraints = [
            models.UniqueConstraint(fields=["mini"], name="minibasins_data_unique_mini"),
        ]
        ordering = ['mini']

    def __str__(self):
        return 'Mini {} | ordem {} | sub {}'.format(self.mini,self.ordem, self.sub)


# SAGUI-specific models
class RainFall(models.Model):
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

    def __str__(self):
        return 'Cell_id {} | date {} | rain {}'.format(self.cell_id, self.date, self.rain)


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
        db_table = 'hyfaa_stations'
        # managed = False
        constraints = [
            models.UniqueConstraint(fields=["name"], name="hyfaa_stations_name_unique"),
        ]
        ordering = ['name']

    def __str__(self):
        # return '#{} {} ( riv. {} / {})'.format(self.id, self.name, self.river, self.minibasin)

        return '#{} {} '.format(self.id, self.name)


class StationsReferenceFlowPeriod(models.Model):
    id = models.AutoField(primary_key=True)
    period = models.CharField(max_length=20, null=False, unique=True, default="2010-2020")

    class Meta:
        verbose_name = 'Stations reference flow period: period (years) that can be used for the pre-global warming data series'
        db_table = 'stations_reference_flow_period'
    def __str__(self):
        return self.period


class StationsReferenceFlow(models.Model):
    id = models.AutoField(primary_key=True)
    period = models.ForeignKey(StationsReferenceFlowPeriod, on_delete=models.CASCADE)
    day_of_year = models.SmallIntegerField()
    station = models.ForeignKey(Stations, on_delete=models.CASCADE)
    flow= models.SmallIntegerField()

    class Meta:
        verbose_name = 'Stations reference flow values: values from pre-global warming era'
        db_table = 'stations_reference_flow'
        unique_together = (('period', 'day_of_year', 'station'),)
        indexes = [
            models.Index(fields=['-day_of_year']),
            models.Index(fields=['station_id', 'day_of_year']),
        ]
        ordering = ['day_of_year']

    def __str__(self):
        return '{} ( station. {} )'.format(self.period, self.station_id)


class StationsWithFlowAlerts(geomodels.Model):
    id = models.IntegerField(null=False, primary_key=True)
    name = models.CharField(max_length=50, null=False)
    river = models.CharField(max_length=50, null=True, blank=True)
    minibasin = models.IntegerField(null=False)
    levels = models.JSONField()
    geom = geomodels.PointField(null=True)

    class Meta:
        verbose_name = 'Stations with alert codes (View)'
        db_table = 'stations_with_flow_alerts'
        managed = False
        ordering = ['id']

    def __str__(self):
        return '{} ( riv. {} / {})'.format(self.name, self.river, self.minibasin)


class StationsWithFlowPrevi(geomodels.Model):
    id = models.IntegerField(null=False, primary_key=True)
    name = models.CharField(max_length=50, null=False)
    river = models.CharField(max_length=50, null=True, blank=True)
    minibasin = models.IntegerField(null=False)
    levels = models.JSONField()
    geom = geomodels.PointField(null=True)

    class Meta:
        verbose_name = 'Stations with previ codes (View)'
        db_table = 'stations_with_flow_previ'
        managed = False
        ordering = ['id']

    def __str__(self):
        return '{} ( riv. {} / {})'.format(self.name, self.river, self.minibasin)


class ImportState(models.Model):
    tablename = models.CharField(max_length=50, null=False, primary_key=True)
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


class SaguiConfig(models.Model):
    max_ordem = models.SmallIntegerField('Max ordem', default=12,
            help_text="Minibasins will be filtered on this value (keep only minibasins with ordem value >= to this one")

    class Datasets(models.TextChoices):
        MGBSTANDARD = 'mgbstandard'
        ASSIMILATED = 'assimilated'

    use_dataset = models.CharField(
        max_length=15,
        choices=Datasets.choices,
        default=Datasets.ASSIMILATED,
        help_text = "To determine the alert level for a given stations, its thresholds must be compared with the current values from one dataset. We can choose here which one to use",
    )

    class Meta:
        verbose_name = 'SAGUI configuration'

    def __str__(self):
        return 'Max ordem: {} | Dataset used: {}'.format(self.max_ordem, self.use_dataset)
