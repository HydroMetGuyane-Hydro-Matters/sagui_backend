from rest_framework import serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from .models import Stations, StationsWithFlowAlerts
#
# class StationsWithFlowAlertsNonGeoSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = StationsWithFlowAlerts
#         fields = ('id', 'name', 'river', 'minibasin', 'levels')


class StationsWithFlowAlertsGeoSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = StationsWithFlowAlerts
        geo_field = "geom"
        fields = ('id', 'name', 'river', 'minibasin', 'levels')


class StationRecordSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    minibasin = serializers.IntegerField()
    city = serializers.CharField()
    data = serializers.JSONField()