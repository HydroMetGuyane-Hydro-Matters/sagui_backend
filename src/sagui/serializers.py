from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from .models import Stations

class StationsNonGeoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Stations
        fields = ('id', 'name', 'minibasin_id')


class StationsGeoSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = Stations
        geo_field = "geom"
        fields = ('id', 'name', 'minibasin_id')


class StationRecordSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    minibasin = serializers.IntegerField()
    city = serializers.CharField()
    data = serializers.JSONField()