from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from .models import Stations, StationsWithAlerts

class StationsNonGeoSerializer(serializers.ModelSerializer):
    class Meta:
        model = StationsWithAlerts
        fields = ('id', 'name', 'river', 'minibasin', 'levels')


class StationsGeoSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = StationsWithAlerts
        geo_field = "geom"
        fields = ('id', 'name', 'river', 'minibasin', 'levels')


class StationRecordSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    minibasin = serializers.IntegerField()
    city = serializers.CharField()
    data = serializers.JSONField()