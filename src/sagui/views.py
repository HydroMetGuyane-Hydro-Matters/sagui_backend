from collections import Counter
import csv
from datetime import date, timedelta, datetime
import logging
import statistics

from django.core import serializers
from django.db import connection
from django.http import HttpResponse
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.reverse import reverse
from rest_framework.settings import api_settings
from rest_framework_csv.renderers import CSVRenderer
from rest_framework.views import APIView
from django.contrib.gis.geos import Point
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample

from sagui import serializers, models
from sagui.models import Stations, DataMgbStandard, DataAssimilated, DataForecast, StationsWithFlowAlerts, SaguiConfig

logger = logging.getLogger(__name__)

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
    """
    Get the list of stations, as geojson.
    For each station, a levels dictionnary provides the prevision levels on this station, 
    """
    serializer_class = serializers.StationsWithFlowAlertsGeoSerializer
    pagination_class = LargeResultsSetPagination
    queryset = models.StationsWithFlowAlerts.objects.all()


class StationsPreviList(generics.ListAPIView):
    serializer_class = serializers.StationsWithFlowPreviGeoSerializer
    pagination_class = LargeResultsSetPagination
    queryset = models.StationsWithFlowPrevi.objects.all()


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
    Get Station records for flow previ graphics:
    retrieve the 10 last days of flow data + append the forecast data.
     (use the id field as can be seen on /api/v1/flow_previ/stations).
    """
    serializer_class=serializers.StationFlowPreviRecordsSerializer
    renderer_classes = tuple(api_settings.DEFAULT_RENDERER_CLASSES) + (CSVRenderer,)

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
        dates_list = [start_date + timedelta(days=n+1) for n in range(int((end_date - start_date).days))]
        doy_list = [d.strftime('%j') for d in dates_list]
        reference_records = models.StationsReferenceFlow.objects.filter(station_id__exact=id,
                                                     day_of_year__in=doy_list,
                                                     ).order_by('day_of_year')
        reference_records_as_dict = {
            str(r.day_of_year): r.value for r in reference_records
        }
        reference_data = [{
            "source": '2010-2020',
            "date": d.strftime("%Y-%m-%d"),
            "flow": round(reference_records_as_dict[d.strftime('%j').lstrip("0")]),
        } for d in dates_list]

        # 5. Generate the output structure and send it
        # Handle special case where format is CSV (serializer cannot automatically generate a usable CSV here)
        if format == 'csv' or request.query_params.get('format', None) == 'csv'\
                or request.accepted_media_type == 'text/csv':
            return self._response_as_csv(id, [mgb_or_assim_data, forecast_data])
        

        station_record = {
            'id': station.id,
            'minibasin': station.minibasin_id,
            'city': station.name,
            'river': station.river,
            'data': {
                'flow': mgb_or_assim_data,
                'forecast': forecast_data,
                'references': [{
                    'id': '2010-2020',
                    'data': reference_data
                },
                ],
            },
        }
        serializer = serializers.StationFlowPreviRecordsSerializer(station_record, many=False)
        return Response(serializer.data)


    def _response_as_csv(self, id, datasets):
        # Create the HttpResponse object with the appropriate CSV header.
        response = HttpResponse(
            content_type='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename="station_{id}_previ_record.csv"'.format(id=id)
            },
        )
        writer = csv.writer(response)
        writer.writerow(['source', 'date', 'flow', 'flow_mad'])
        for dataset in datasets:
            for r in dataset:
                writer.writerow([r.get('source'), r.get('date'), r.get('flow'), r.get('flow_mad')])

        return response


class StationFlowRecordsById(generics.GenericAPIView):
    """
    Get the flow data on the station (use the id field as can be seen on /api/v1/flow_alert/stations).
    Retrieves the n last days of data, where n is defined by the duration parameter, in days
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
        ref_date = None
        try:
            ref_date = models.DataAssimilated.objects.latest('date').date
        except:
            logger.error("Impossible to retrieve last date for data from hyfaa_data_assimilated table. Are you sure it's not empty ?")
            return Response(status=status.HTTP_400_BAD_REQUEST)
        from_date = ref_date - timedelta(days=nb_days_backward)

        # 1. Get station records
        station = models.Stations.objects.filter(id__exact=id)
        if not station:
            logger.error("No record found for station with id ", id)
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

        if not forecast_records:
            logger.error("No forecasts found for station with id ", id)
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


class Dashboard(APIView):
    """
    Get data for dashboard display
    """
    serializer_class=serializers.DashboardEntrySerializer

    def get(self, request, format=None):
        dash_entries = []
        # 1. flow_previ entry
        # Get anomaly stats and codes over the stations
        anomaly = None
        try:
            # Try to fetch the name of the table for source data from the saguiconfig table
            tablename = 'hyfaa_data_assimilated'
            config = SaguiConfig.objects.first()
            if config:
                tablename = 'hyfaa_data_' + config.use_dataset

            with connection.cursor() as cursor:
                query = '''
SELECT  ROUND(AVG(flow_anomaly)), guyane.anomaly_to_alert_level(AVG(flow_anomaly)) AS code_avg, 
        ROUND(MIN(flow_anomaly)), guyane.anomaly_to_alert_level(MIN(flow_anomaly)) AS code_min, 
        ROUND(MAX(flow_anomaly)), guyane.anomaly_to_alert_level(MAX(flow_anomaly)) AS code_max
FROM guyane.{tbl} a, guyane.hyfaa_stations s 
WHERE a.cell_id = s.minibasin_id 
AND a."date" IN (SELECT DISTINCT "date" FROM guyane.{tbl} ORDER BY "date" DESC LIMIT 1);
                '''.format(tbl=tablename)
                cursor.execute(query)
                rec = cursor.fetchone()
        except Exception as error:
            logger.error("Exception while fetching Dashboard data:", error)
            logger.error("Exception TYPE:", type(error))

        if rec:
            # get the code for the anomaly with highest asbsolute value
            global_alert_level = rec[1]
            dash_entries.append({
                "id": "flow_previ",
                "alert_code": global_alert_level,
                "attributes": {
                    "anomaly_avg": rec[0],
                    "anomaly_min": rec[2],
                    "anomaly_max": rec[4],
                }
            })

        # 2. flow_alerts entry
        # flow_alert_levels = ['f3', 'f2', 'f1', 'd3', 'd2', 'd1', 'n']
        flow_alert_levels = ['f3', 'f2', 'f1', 'd2', 'n']
        with connection.cursor() as cursor:
            cursor.execute('SELECT levels->0->>\'level\' AS l FROM guyane.stations_with_flow_alerts')
            recs = cursor.fetchall()

        rec_levels = [r[0] for r in recs] if recs else []
        levels_count = Counter(rec_levels)
        levels_stats = { k:levels_count[k] for k in flow_alert_levels}
        global_alert_level ='undefined'
        for lev in flow_alert_levels:
            if lev in rec_levels:
                global_alert_level = lev
                break

        dash_entries.append({
            "id": "flow_alerts",
            "alert_code": global_alert_level,
            "attributes": levels_stats
        })

        # 3. Rain alert entry
        # we will use thresholds 5, 20 and 50mm
        alert_levels = [
            (50, 'r3'),
            (20, 'r2'),
            (5, 'r1'),
            (0, 'n'),
        ]
        alert_code = 'undefined'

        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT ROUND(avg((values->0->>\'rain\')::numeric),1) AS l FROM guyane.rainfall_minibasin_aggregated_geo')
                rec = cursor.fetchone()
                mean_rain = rec[0] if rec else None
                for lev in alert_levels:
                    if mean_rain >= lev[0]:
                        alert_code = lev[1]
                        break
        except Exception as error:
            logger.error("Exception while fetching Dashboard data:", error)
            logger.error("Exception TYPE:", type(error))

        dash_entries.append({
            "id": "rain_alerts",
            "alert_code": alert_code,
            "attributes": {}
        })

        # 4. Atmospheric alert entry
        dash_entries.append({
            "id": "atmo_alerts",
            "alert_code": "undefined",
            "attributes": {}
        })

        serializer = serializers.DashboardEntrySerializer(dash_entries, many=True)
        return Response(serializer.data)