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


class DataMgbStandard(AbstractHyfaaData):
    flow_expected = models.FloatField(null=True, help_text='Expected value. Calculated using a floating median, over the flow_median values taken on the day surrounding the current day (+ or - 10 days around), during the previous years')
    flow_anomaly = models.FloatField(null=True, help_text='Represents the anomaly compared to expected data. Formula is 100 * (anomaly - expected) / expected')

    class Meta:
        db_table = 'hyfaa\".\"data_mgbstandard'
        verbose_name = 'MGB hydrological data, calculated using HYFAA scheduler, without assimilation'
        constraints = [
            models.UniqueConstraint(fields=["cell_id", "date"], name="data_mgbstandard_unique_cellid_day"),
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

    class Meta:
        db_table = 'hyfaa\".\"data_forecast'
        # managed = False
        verbose_name = 'Forecast MGB hydrological data, calculated using HYFAA scheduler, with assimilation'
        constraints = [
            models.UniqueConstraint(fields=["cell_id", "date"], name="data_forecast_unique_cellid_day"),
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
        db_table = 'hyfaa\".\"data_assimilated'
        # managed = False
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
        db_table = 'geospatial\".\"drainage'
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
        # managed = False
        constraints = [
            models.UniqueConstraint(fields=["name"], name="stations_name_unique"),
        ]
        ordering = ['name']

    def __str__(self):
        return '{} ( riv. {} / {})'.format(self.name, self.river, self.minibasin)