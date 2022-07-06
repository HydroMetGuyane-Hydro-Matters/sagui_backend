from datetime import date, timedelta, datetime

from django.core import serializers
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.reverse import reverse
from django.contrib.gis.geos import Point
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample

from sagui import serializers, models
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


class StationsAlertList(generics.ListAPIView):
    serializer_class = serializers.StationsWithFlowAlertsGeoSerializer
    pagination_class = LargeResultsSetPagination
    queryset = models.StationsWithFlowAlerts.objects.all()


class StationsPreviList(generics.ListAPIView):
    serializer_class = serializers.StationsWithFlowPreviGeoSerializer
    pagination_class = LargeResultsSetPagination
    queryset = models.StationsWithFlowPrevi.objects.all()

#
# class StationsAsGeojson(generics.ListAPIView):
#     serializer_class = StationsWithFlowAlertsGeoSerializer
#     pagination_class = LargeResultsSetPagination
#     queryset = StationsWithFlowAlerts.objects.all()


def _get_minibasin_id_from_station_id(id):
    """
    Retrieve the minibasin id from the station's id: needed to get to the flow data
    :param id: station's id
    :return: cell (minibasin) id
    """
    station = Stations.objects.filter(id__exact=id)
    if not station:
        return None
    station = station.first()
    return station.minibasin_id


def _get_mgb_or_assim_data(cell_id, start_date, end_date, with_expected=False):
    """
    Get data from mgbstandard or assimilated tables and produce a list of records suited for display
    in a graph
    Whether we get the mgbstandard or assimilated data is configured in the table sagui_saguiconfig
    :param cell_id:
    :param start_date:
    :param end_date:
    :param with_expected: if True, add `flow_expected` value in the records
    :return:
    """
    # Get the name of the source to tap from
    dataset_source = 'assimilated'
    config = models.SaguiConfig.objects.first()
    if config:
        dataset_source = config.use_dataset

    mgb_or_assim_data = []
    if dataset_source == 'assimilated':
        # Get results for last 10 days
        assimrecords = models.DataAssimilated.objects.filter(cell_id__exact=cell_id,
                                     date__gt=start_date,
                                     date__lte=end_date,
                                     ).order_by('date')
        if with_expected:
            mgb_or_assim_data = [{
                "source": dataset_source,
                "date": r.date.strftime("%Y-%m-%d"),
                "flow": round(r.flow_median),
                "flow_mad": round(r.flow_mad),
                "flow_expected": round(r.flow_expected),
            } for r in assimrecords]
        else:
            mgb_or_assim_data = [{
                "source": dataset_source,
                "date": r.date.strftime("%Y-%m-%d"),
                "flow": round(r.flow_median),
                "flow_mad": round(r.flow_mad),
            } for r in assimrecords]
    else:  # mgbstandard
        # Get results for last 10 days
        mgbrecords = models.DataMgbStandard.objects.filter(cell_id__exact=cell_id,
                                     date__gt=start_date,
                                     date__lte=end_date,
                                     ).order_by('date')
        if with_expected:
            mgb_or_assim_data = [{
                "source": dataset_source,
                "date": r.date.strftime("%Y-%m-%d"),
                "flow": round(r.flow_mean),
                "flow_mad": 0,
                "flow_expected": round(r.flow_expected),
            } for r in mgbrecords]
        else:
            mgb_or_assim_data = [{
                "source": dataset_source,
                "date": r.date.strftime("%Y-%m-%d"),
                "flow": round(r.flow_mean),
                "flow_mad": 0,
            } for r in mgbrecords]
    return mgb_or_assim_data


class StationsPreviRecordsById(generics.GenericAPIView):
    """
    Get Station records for flow previ graphics
    """
    serializer_class=serializers.StationFlowPreviRecordsSerializer
    @extend_schema(
        # extra parameters added to the schema
        parameters=[
            OpenApiParameter("id", required=True, type=int, location=OpenApiParameter.PATH,
                                 description="Station identifier, as can be found on /api/v1/stations/"
                             ),
            OpenApiParameter(name='duration', description='Duration time to extract, in days', required=False,
                             type=int, default=10),
        ],
    )

    def get(self, request, id, format=None):
        """Retrieve some latest assimilated records and append forecast data after them"""
        # In the following code, we'll mostly use the cell_id, not the station id
        cell_id = _get_minibasin_id_from_station_id(id)

        nb_days_backward = request.query_params.get('duration', 10)
        nb_days_backward = int(nb_days_backward)

        # Get last date available from the DB
        ref_date = models.DataAssimilated.objects.latest('date').date
        from_date = ref_date - timedelta(days=nb_days_backward)

        # 1. Get station records
        station = models.Stations.objects.filter(id__exact=id)
        if not station:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        station = station.first()
        station_data = dict()

        # 2. Get a 10-days recordset from mgb / assimilated dataset
        mgb_or_assim_data = _get_mgb_or_assim_data(cell_id, from_date, ref_date)

        # 3. Get forecast data
        forecast_records = models.DataForecast.objects.filter(cell_id__exact=cell_id,
                                                     date__gt=ref_date,
                                                     ).order_by('date')
        forecast_data = [{
                        "source": "forecast",
                        "date": r.date.strftime("%Y-%m-%d"),
                        "flow": round(r.flow_median),
                        "flow_mad": round(r.flow_mad),
                    } for r in forecast_records ]

        # 4. Get pre-globalwarming reference data
        # This is a tricky one, since we deal with day_of_year in the reference table
        # Get date interval
        start_date = ref_date - timedelta(days=nb_days_backward)
        end_date = forecast_records.last().date
        dates_list = [start_date + timedelta(days=n) for n in range(int((end_date - start_date).days))]
        doy_list = [d.strftime('%j') for d in dates_list]
        reference_records = models.StationsReferenceFlow.objects.filter(station_id__exact=id,
                                                     day_of_year__in=doy_list,
                                                     ).order_by('day_of_year')
        reference_records_as_dict = {
            str(r.day_of_year): r.value for r in reference_records
        }
        reference_data = [{
            "source": "reference",
            "date": d.strftime("%Y-%m-%d"),
            "flow": round(reference_records_as_dict[d.strftime('%j')]),
        } for d in dates_list]

        # 5. Generate the output structure and send it
        station_record = {
            'id': station.id,
            'minibasin': station.minibasin_id,
            'city': station.name,
            'river': station.river,
            'data': {
                'flow': mgb_or_assim_data,
                'forecast': forecast_data,
                'reference': reference_data,
            },
        }
        serializer = serializers.StationFlowPreviRecordsSerializer(station_record, many=False)
        return Response(serializer.data)


def get_station_mgbstandard_record(cell_id, ref_date, duration=365):
    """
    Get data from mgb_standard dataset
    :param id: cell id
    :param ref_date: latest date to fetch
    :param duration: duration, in days (backwards)
    :return:
    """
    from_date = ref_date - timedelta(days=duration)
    records = models.DataMgbStandard.objects.filter(cell_id__exact=cell_id,
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
    records = models.DataAssimilated.objects.filter(cell_id__exact=cell_id,
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
    mgbrecords = models.DataMgbStandard.objects.filter(cell_id__exact=cell_id,
                                     date__gt=from_date,
                                     date__lte=ref_date,
                                     ).order_by('date')
    records = models.DataForecast.objects.filter(cell_id__exact=cell_id,
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


class StationFlowRecordsById(generics.GenericAPIView):
    """
    Get Station records
    """
    serializer_class=serializers.StationFlowAlertRecordsSerializer
    @extend_schema(
        # extra parameters added to the schema
        parameters=[
            OpenApiParameter("id", required=True, type=int, location=OpenApiParameter.PATH,
                                 description="Station identifier, as can be found on /api/v1/stations/"
                             ),
            OpenApiParameter(name='duration', description='Duration time to extract, in days', required=False,
                             type=int, default=365),
        ],
    )

    def get(self, request, id,  format=None):
        # In the following code, we'll mostly use the cell_id, not the station id
        cell_id = _get_minibasin_id_from_station_id(id)
        # Get last date available from the DB
        nb_days_backward = request.query_params.get('duration', 365)
        nb_days_backward = int(nb_days_backward)

        # Get last date available from the DB
        ref_date = models.DataAssimilated.objects.latest('date').date
        from_date = ref_date - timedelta(days=nb_days_backward)

        # 1. Get station records
        station = models.Stations.objects.filter(id__exact=id)
        if not station:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        # get station record as dict (will serve for threshold data)
        station_as_dict = station.values()[0]
        #get station as object, simpler
        station = station.first()
        station_data = dict()


        # 2. Get a duration-days recordset from mgb / assimilated dataset
        mgb_or_assim_data = _get_mgb_or_assim_data(cell_id, from_date, ref_date, with_expected=True)

        # 3. Get forecast data
        forecast_records = models.DataForecast.objects.filter(cell_id__exact=cell_id,
                                                     date__gt=ref_date,
                                                     ).order_by('date')
        forecast_data = [{
                        "source": "forecast",
                        "date": r.date.strftime("%Y-%m-%d"),
                        "flow": round(r.flow_median),
                        "flow_mad": round(r.flow_mad),
                    } for r in forecast_records ]


        # 4. Generate the output structure and send it
        station_record = {
            'id': station.id,
            'minibasin': station.minibasin_id,
            'city': station.name,
            'river': station.river,
            'data': {
                'flow': mgb_or_assim_data,
                'forecast': forecast_data,
            },
            'thresholds': [
                {
                    k: v for k,v in station_as_dict.items() if (k.startswith("threshold") and v != -9999)
                }

            ]
        }

        serializer = serializers.StationFlowAlertRecordsSerializer(station_record, many=False)
        return Response(serializer.data)