from datetime import date, timedelta, datetime

from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.reverse import reverse
from django.contrib.gis.geos import Point
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample

from sagui.serializers import StationsWithFlowAlertsGeoSerializer, StationRecordSerializer
from sagui.models import Stations, DataMgbStandard, DataAssimilated, DataForecast, StationsWithFlowAlerts


@api_view(['GET'])
def api_root(request, format=None):
    return Response({
        'stations-list': reverse('get-stations-list', request=request, format=format),
        'swagger-ui': reverse('swagger-ui', request=request, format=format),
        'openapi-schema': reverse('openapi-schema', request=request, format=format),
    })


class LargeResultsSetPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 10000


class StationsList(generics.ListAPIView):
    serializer_class = StationsWithFlowAlertsGeoSerializer
    pagination_class = LargeResultsSetPagination
    queryset = StationsWithFlowAlerts.objects.all()

#
# class StationsAsGeojson(generics.ListAPIView):
#     serializer_class = StationsWithFlowAlertsGeoSerializer
#     pagination_class = LargeResultsSetPagination
#     queryset = StationsWithFlowAlerts.objects.all()


def get_station_mgbstandard_record(cell_id, ref_date, duration=365):
    """
    Get data from mgb_standard dataset
    :param id: cell id
    :param ref_date: latest date to fetch
    :param duration: duration, in days (backwards)
    :return:
    """
    from_date = ref_date - timedelta(days=duration)
    records = DataMgbStandard.objects.filter(cell_id__exact=cell_id,
                                     date__gt=from_date,
                                     date__lte=ref_date,
                                     ).order_by('date')
    data_dict = {
        'mgbstandard': [ {
              "date": r.date.strftime("%Y-%m-%d"),
              "flow": round(r.flow_mean),
              "expected": round(r.flow_expected),
          } for r in records ]
    }
    return data_dict


def get_station_assimilated_record(cell_id, ref_date, duration=365):
    """
    Get data from mgb_standard dataset
    :param id: cell id
    :param ref_date: latest date to fetch
    :param duration: duration, in days (backwards)
    :return:
    """
    from_date = ref_date - timedelta(days=duration)
    records = DataAssimilated.objects.filter(cell_id__exact=cell_id,
                                     date__gt=from_date,
                                     date__lte=ref_date,
                                     ).order_by('date')
    data_dict = {
        'assimilated': [ {
              "date": r.date.strftime("%Y-%m-%d"),
              "flow": round(r.flow_median),
              "flow_mad": round(r.flow_mad),
              "expected": round(r.flow_expected),
          } for r in records ]
    }
    return data_dict


def get_station_forecast_record(cell_id, ref_date, duration=365):
    """
    Get data from mgb_standard dataset
    :param id: cell id
    :param ref_date: latest date to fetch
    :param duration: duration, in days (backwards)
    :return:
    """
    max_recs = min(duration, 20)
    from_date = ref_date - timedelta(days=max_recs)
    # Retrieve some latest mgb_standard records and append forecast data after them
    mgbrecords = DataMgbStandard.objects.filter(cell_id__exact=cell_id,
                                     date__gt=from_date,
                                     date__lte=ref_date,
                                     ).order_by('date')
    records = DataForecast.objects.filter(cell_id__exact=cell_id,
                                     date__gt=ref_date,
                                     ).order_by('date')

    data_dict = {
        'forecast': [ {
              "source": "mgbstandard",
              "date": r.date.strftime("%Y-%m-%d"),
              "flow": round(r.flow_mean),
              "flow_mad": 0,
          } for r in mgbrecords
        ] +
        [ {
              "source": "forecast",
              "date": r.date.strftime("%Y-%m-%d"),
              "flow": round(r.flow_median),
              "flow_mad": round(r.flow_mad),
          } for r in records
        ]
    }

    return data_dict


def get_records_full_mode(id, ref_date, duration):
    data_dict = {}
    data_dict['mgbstandard'] = get_station_mgbstandard_record(id, ref_date, duration)['mgbstandard']
    data_dict['assimilated'] = get_station_assimilated_record(id, ref_date, duration)['assimilated']
    data_dict['forecast'] = get_station_forecast_record(id, ref_date, duration)['forecast']
    return data_dict


class StationRecordsById(generics.GenericAPIView):
    """
    Get Station records
    """
    serializer_class="StationRecordSerializer"
    @extend_schema(
        # extra parameters added to the schema
        parameters=[
            OpenApiParameter("id", required=True, type=int, location=OpenApiParameter.PATH,
                                 description="Station identifier, as can be found on /api/v1/stations/"
                             ),
            OpenApiParameter(name='dataserie', location=OpenApiParameter.PATH,
                             enum=['all', 'mgbstandard', 'assimilated', 'forecast'],
                             description='Serie of data to fetch. One of all|mgbstandard|assimilated|forecast',
                             required=True, type=str, default='mgbstandard'),
            OpenApiParameter(name='duration', description='Duration time to extract, in days', required=False,
                             type=int, default=10),
        ],
    )

    def get(self, request, id, dataserie, format=None):
        # ref_date = datetime.now()
        # Get last date available from the DB
        ref_date = DataMgbStandard.objects.latest('date').date
        duration = request.query_params.get('duration')
        if not duration:
            duration = 365
        else:
            duration = int(duration)
        from_date = ref_date - timedelta(days=duration)

        station = Stations.objects.filter(id__exact=id)
        station = station.first()
        station_data = dict()
        if dataserie == "all":
            station_data = get_records_full_mode(station.minibasin_id, ref_date, duration)
        elif dataserie == "mgbstandard":
            station_data = get_station_mgbstandard_record(station.minibasin_id, ref_date, duration)
        elif dataserie == "assimilated":
            station_data = get_station_assimilated_record(station.minibasin_id, ref_date, duration)
        elif dataserie == "forecast":
            station_data = get_station_forecast_record(station.minibasin_id, ref_date, duration)
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST)



        # Generate a simpler object structure for output
        station_record = {
            'id': station.id,
            'minibasin': station.minibasin_id,
            'city': station.name,
            'river': station.river,
            'data': station_data,
        }

        serializer = StationRecordSerializer(station_record, many=False)
        return Response(serializer.data)