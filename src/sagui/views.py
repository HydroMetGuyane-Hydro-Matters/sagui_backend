from collections import Counter
import csv
from datetime import date, timedelta, datetime
import logging
import os
import re
from glob import glob

from django.core import serializers
from django.http import HttpResponse
from django.contrib.staticfiles.storage import staticfiles_storage
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.decorators import api_view
from rest_framework.reverse import reverse
from rest_framework.settings import api_settings
from rest_framework_csv.renderers import CSVRenderer
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter
from django.conf import settings
from django.shortcuts import render

from sagui import serializers, models
from sagui.utils import atmo, rain, \
    stations_forecast as stations_forecast_utils, \
    stations_alert as stations_alert_utils

logger = logging.getLogger(__name__)


def html_dashboard(request):
    # Collect flow previ data
    forecast_data = stations_forecast_utils.get_global_alert_info()
    forecast_histogram = forecast_data['histogram']

    forecast_data_summary = {
        "Normal": forecast_histogram['n'],
        "En alerte": sum([v for k, v in forecast_histogram.items() if k!='n']),
    }

    # Collect flow alert data
    alerts_data = stations_alert_utils.get_global_alert_info()
    alerts_histogram = alerts_data['histogram']

    alerts_data_summary = {
        "Normal": alerts_histogram['n'],
        "En alerte": sum([v for k, v in alerts_histogram.items() if k!='n']),
    }

    # Collect rain data
    rain_data = rain.get_global_alert_info()
    rain_histogram = rain_data['histogram']
    for k,v in rain_histogram.items():
        rain_histogram[k] = int(v)

    rain_data_summary = {
        "Normal": int(rain_histogram['n']),
        "En alerte": int(sum([v for k, v in rain_histogram.items() if k!='n'])),
    }

    # Collect atmo data
    atmo_data = atmo.get_global_alert_info()
    atmo_histogram = atmo_data['histogram']
    for k,v in atmo_histogram.items():
        atmo_histogram[k] = int(v)

    atmo_data_summary = {
        "Normal": int(atmo_histogram['a0']),
        "En alerte": int(sum([v for k, v in atmo_histogram.items() if k!='a0'])),
    }


    flow_colors = {
      "Normal": "rgba(0, 235, 108)",
      "En alerte": "rgba(255, 69, 56)",
      "n": "rgba(0, 235, 108)",
      "a": "rgba(255, 69, 56)",
      "d1": "rgba(255, 235, 59)",
      "f1": "rgba(255, 235, 59)",
      "d2": "rgba(253, 122, 0)",
      "f2": "rgba(253, 122, 0)",
      "d3": "rgba(255, 69, 56)",
      "f3": "rgba(255, 69, 56)",
      "r1": "rgba(255, 235, 59)",
      "r2": "rgba(253, 122, 0)",
      "r3": "rgba(255, 69, 56)",
      "a0": "#00FFFF89",
      "a1": "#54C372FF",
      "a2": "#FFFF00FF",
      "a3": "#EA4335FF",
      "a4": "#980000FF",
      "a5": "#674EA7FF",
    }

    context = {
        'flow_colors': flow_colors,
        'forecast_data_summary': forecast_data_summary,
        'forecast_histogram': forecast_histogram,
        'alerts_data_summary': alerts_data_summary,
        'alerts_histogram': alerts_histogram,
        'rain_histogram': rain_histogram,
        'rain_data_summary': rain_data_summary,
        'atmo_histogram': atmo_histogram,
        'atmo_data_summary': atmo_data_summary,
        'title': 'SAGUI dashboard',
    }
    return render(request, 'sagui/dashboard.html', context)


def html_dashboard_flow(request):
    stations_with_forecast = models.StationsWithFlowPrevi.objects.order_by('-name')
    context = {
        'stations_with_forecast': stations_with_forecast,
        'title': 'SAGUI',
    }
    return render(request, 'sagui/dashboard_flow.html', context)
#
# class IndexView(generic.ListView):
#     template_name = 'sagui/dashboard.html'
#     context_object_name = 'stations_with_alerts'
#
#     def get_queryset(self):
#         """Return the last five published questions."""
#         return StationsWithFlowAlerts.objects.order_by('-name')

@api_view(['GET'])
def api_root(request, format=None):
    return Response({
        'dashboard': reverse('dashboard', request=request, format=format),
        'flow-previ-stations-list': reverse('flow-previ-get-stations-list', request=request, format=format),
        'flow-alerts-stations-list': reverse('flow-alerts-get-stations-list', request=request, format=format),
        # 'atmo-get-classes': reverse('atmo-get-classes', request=request, format=format),
        'atmo-alerts-rasters': reverse('atmo-alerts-rasters', request=request, format=format),
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
    station = models.Stations.objects.filter(id__exact=id)
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
    lookup_field = 'id'

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
        reference_periods = models.StationsReferenceFlowPeriod.objects.all().order_by('-period')
        reference_records = models.StationsReferenceFlow.objects.filter(station_id__exact=id,
                                                     day_of_year__in=doy_list,
                                                     ).order_by('day_of_year')
        reference_records_as_dict = {
            f'{r.day_of_year}': r.flow for r in reference_records
        }
        reference_data = [{
            "source": '2010-2020',
            "date": d.strftime("%Y-%m-%d"),
            "flow": round(reference_records_as_dict[d.strftime('%j').lstrip("0")]),
        } for d in dates_list]
        reference_records_as_dict = {
            f'{r.period}/{r.day_of_year}': r.flow for r in reference_records
        }
        # reference_data = [{
        #     "period": p.period,
        #     'data'
        #     "date": d.strftime("%Y-%m-%d"),
        #     "flow": round(reference_records_as_dict[d.strftime('%j').lstrip("0")]),
        # } for p in reference_periods]

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
            'unit': 'm³/sec',
            'data': {
                'flow': mgb_or_assim_data,
                'forecast': forecast_data,
                'references': [
                #     {
                #     'id': '2010-2020',
                #     'data': reference_data
                # },
                ],
            },
        }
        for p in reference_periods:
            station_record['data']['references'].append({
                'id': p.period,
                'data': [{
                    "source": p.period,
                    "date": d.strftime("%Y-%m-%d"),
                    "flow": round(reference_records_as_dict[f"{p.period}/{d.strftime('%j').lstrip('0')}"]),
                } for d in dates_list]
            })
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
    lookup_field = 'id'

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
            'unit': 'm³/sec',
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
        # Get anomaly stats and alert codes over the stations
        rec = stations_forecast_utils.get_global_alert_info()
        dash_entries.append({
            "id": "flow_previ",
            "alert_code": rec['global_alert_level'],
            "histogram": rec['histogram'],
            "description": "Alert level based on the anomaly relative to the 'pre-global warming' historical reference data from last decade. It is computed only on the location of the stations, where we have such data",
            "attributes": rec['stats'],
        })

        # 2. flow_alerts entry
        rec = stations_alert_utils.get_global_alert_info()
        dash_entries.append({
            "id": "flow_alerts",
            "alert_code": rec['global_alert_level'],
            "description": "Flow alert level, computed over the stations locations",
            "histogram": rec['histogram'],
            "attributes": {},
        })

        # 3. Rain alert entry
        # we will use thresholds 5, 20 and 50mm
        rec = rain.get_global_alert_info()
        dash_entries.append({
            "id": "rain_alerts",
            "alert_code": rec['global_alert_level'],
            "histogram": rec['histogram'],
            "description": "Rain level alert code (<5mm = normal, <20mm = low, <50mm = medium, above = high) based on sub-basins. Histogram shows mini-basins stats",
            "attributes": {},
        })

        # 4. Atmospheric alert entry
        rec = atmo.get_global_alert_info()
        dash_entries.append({
            "id": "atmo_alerts",
            "alert_code": rec['global_alert_level'],
            "histogram": rec['histogram'],
            "description": "Alert code is expected to range between 0 (no alert) and 5 (extremely bad), based on the classes defined by /api/v1/atmo/classes. At the moment, it is using the '10th_max' value",
            "attributes": rec['stats'],
        })

        serializer = serializers.DashboardEntrySerializer(dash_entries, many=True)
        return Response(serializer.data)


class AtmoAlertCategoriesList(generics.ListAPIView):
    """
    Get the atmo categories data with info necessary to render the pngs and generate a legend.
    """
    serializer_class = serializers.AtmoAlertCategoriesSerializer
    queryset = models.AtmoAlertCategories.objects.all()
    renderer_classes = tuple(api_settings.DEFAULT_RENDERER_CLASSES) + (CSVRenderer,)
    pagination_class = None


class AtmoAlertsFilesList(generics.GenericAPIView):
    """
    Get list and path to Atmospheric aerosol index alerts files:
    retrieve the 10 last days of atmo data
    """
    serializer_class = serializers.AtmoAlertsFilesSerializer
    # renderer_classes = tuple(api_settings.DEFAULT_RENDERER_CLASSES) + (CSVRenderer,)

    @extend_schema(
        # extra parameters added to the schema
        parameters=[
            OpenApiParameter(name='duration', description='Duration time to extract, in days', required=False,
                             type=int, default=10),
        ],
    )

    # hack to get browsable_api working
    def get_queryset(self):
        return {}

    def get(self, request, format=None):
        nb_days_backward = request.query_params.get('duration', 10)
        nb_days_backward = int(nb_days_backward)

        files_path = settings.SAGUI_SETTINGS.get('SAGUI_PATH_TO_ATMO_FILES', '')
        files_list = sorted(glob(f'{files_path}/*_aai.png'), reverse=True)[:10]

        results = {
            'count': len(files_list),
            'description': 'map of atmospheric alerts based on Sentinel5P absorbing aerosol index data',
            'extent': {
                'east': -57,
                'south': 1,
                'west': -50,
                'north': 7,
            },
            'classes': reverse('atmo-get-classes', request=request, format=format),
            'legend': self.request.build_absolute_uri('/atmo/styled/legend.png'),
            'results': [],
        }
        for f in files_list:
            d = datetime.strptime(re.search(r"[0-9]{8}", os.path.basename(f))[0], '%Y%m%d').strftime("%Y-%m-%d")
            results['results'].append({
                'date': d,
                'png': self.request.build_absolute_uri(f'/atmo/styled/{os.path.basename(f)}'),
                'wld': self.request.build_absolute_uri(f'/atmo/styled/{os.path.splitext(os.path.basename(f))[0]}.wld'),
                'geotiff': self.request.build_absolute_uri(f'/atmo/styled/{os.path.splitext(os.path.basename(f))[0]}.tif'),
            })

        serializer = serializers.AtmoAlertsFilesSerializer(results, many=False)
        return Response(serializer.data)

