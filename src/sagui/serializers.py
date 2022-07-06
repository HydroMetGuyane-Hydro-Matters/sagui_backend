from rest_framework import serializers
import rest_framework_gis.serializers as gis_serializers
from rest_framework_gis.fields import GeometryField

from .models import Stations, StationsWithFlowAlerts, StationsWithFlowPrevi
#
# class StationsWithFlowAlertsNonGeoSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = StationsWithFlowAlerts
#         fields = ('id', 'name', 'river', 'minibasin', 'levels')


class StationsWithFlowAlertsGeoSerializer(gis_serializers.GeoFeatureModelSerializer):
    class Meta:
        model = StationsWithFlowAlerts
        geo_field = "geom"
        fields = ('id', 'name', 'river', 'minibasin', 'levels')


class StationsWithFlowPreviGeoSerializer(gis_serializers.GeoFeatureModelSerializer):
    class Meta:
        model = StationsWithFlowPrevi
        geo_field = "geom"
        fields = ('id', 'name', 'river', 'minibasin', 'levels')


class FlowRecordSerializer(serializers.Serializer):
    source = serializers.CharField()
    date = serializers.DateField()
    flow = serializers.FloatField()
    flow_mad = serializers.FloatField(required=False)
    flow_expected = serializers.FloatField(required=False)


class ThresholdSerializer(serializers.Serializer):
    threshold_drought = serializers.FloatField(required=False)
    threshold_flood_low = serializers.FloatField(required=False)
    threshold_flood_mid = serializers.FloatField(required=False)
    threshold_flood_high = serializers.FloatField(required=False)


class StationFlowPreviDataSerializer(serializers.Serializer):
    flow = FlowRecordSerializer(many=True)
    forecast = FlowRecordSerializer(many=True)
    reference = FlowRecordSerializer(many=True)


class StationFlowPreviRecordsSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    minibasin = serializers.IntegerField()
    city = serializers.CharField()
    data = StationFlowPreviDataSerializer()


class StationFlowAlertDataSerializer(serializers.Serializer):
    flow = FlowRecordSerializer(many=True)
    forecast = FlowRecordSerializer(many=True)


class StationFlowAlertRecordsSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    minibasin = serializers.IntegerField()
    city = serializers.CharField()
    data = StationFlowAlertDataSerializer()
    thresholds = ThresholdSerializer()