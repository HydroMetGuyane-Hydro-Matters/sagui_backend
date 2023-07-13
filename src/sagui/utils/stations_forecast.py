# Stuff related to stations forecast data

import logging

from django.db import connection

from sagui import models

logger = logging.getLogger(__name__)


def get_global_alert_info():
    global_alert_data = None
    # Compute the global alert code based on mean anomaly over the stations
    try:
        # Try to fetch the name of the table for source data from the saguiconfig table
        tablename = 'hyfaa_forecast_with_assimilated'
        config = models.SaguiConfig.objects.first()
        if config:
            tablename = 'hyfaa_forecast_with_' + config.use_dataset

        with connection.cursor() as cursor:
            query = '''
        -- Use current day+5d for forecast alerts
        WITH most_recent_date AS (
            SELECT DISTINCT "date"+5 AS d FROM guyane.hyfaa_data_assimilated ORDER BY d DESC LIMIT 1
        ) ,
        flows AS (
            SELECT cell_id, flow, "date" FROM guyane.{tbl}
            WHERE "date" IN (SELECT d FROM most_recent_date)
               AND cell_id IN (SELECT DISTINCT minibasin_id FROM guyane.hyfaa_stations)
        ),
        stations_flows AS (
            SELECT s.id AS station_id, f.flow, f."date"
                FROM flows f, guyane.hyfaa_stations s
                WHERE f.cell_id = s.minibasin_id
        ),
        ref_flow_latest AS (
            SELECT * FROM guyane.stations_reference_flow WHERE period_id IN (
            SELECT id FROM guyane.stations_reference_flow_period ORDER BY period DESC LIMIT 1)
        AND day_of_year IN (select DATE_PART('doy', max(d)) FROM most_recent_date)
        ),
        anomalies AS (
            SELECT *,
                   guyane.compute_anomaly(f.flow, r.flow) AS flow_anomaly,
                   guyane.anomaly_to_alert_level(guyane.compute_anomaly(f.flow, r.flow)) AS alert_level
             FROM ref_flow_latest r, stations_flows f
                 WHERE r.station_id = f.station_id
        )
        SELECT  ROUND(AVG(flow_anomaly)) AS val_avg, guyane.anomaly_to_alert_level(AVG(flow_anomaly)) AS code_avg,
            ROUND(MIN(flow_anomaly)) AS val_min, guyane.anomaly_to_alert_level(MIN(flow_anomaly)) AS code_min,
            ROUND(MAX(flow_anomaly)) AS val_max, guyane.anomaly_to_alert_level(MAX(flow_anomaly)) AS code_max
        FROM anomalies
                        '''.format(tbl=tablename)
            cursor.execute(query)
            global_alert_data = cursor.fetchone()

    except Exception as error:
        logger.error("Exception while fetching Dashboard data:", error)
        logger.error("Exception TYPE:", type(error))

    # Get aggregated alert levels
    # Collect flow previ data
    stations_with_previ = models.StationsWithFlowPrevi.objects.all()
    histogram = {
        "d3": 0,
        "d2": 0,
        "d1": 0,
        "n": 0,
        "f1": 0,
        "f2": 0,
        "f3": 0,
    }
    for s in stations_with_previ:
        # We take the forecast data, J+5
        forecast_levels = [lev for lev in s.levels if lev['source'] == 'forecast']
        # J+5 since the list is reversed order by date
        l = forecast_levels[-5]['level']
        # forecast_data[l].append(s.name)
        histogram[l] += 1

    if not global_alert_data:
        return {
            "msg": "Error: could not compute global alert data"
        }

    return {
        # 'global_alert_level': global_alert_data[1] if global_alert_data else '',
        'global_alert_level': global_alert_data[5]  if (abs(global_alert_data[4]) > abs(global_alert_data[2]))
                                                    else global_alert_data[3],
        'histogram': histogram,
        'stats': {
            "anomaly_avg": global_alert_data[0],
            "anomaly_min": global_alert_data[2],
            "anomaly_max": global_alert_data[4],
        },
    }

def get_stations_alert_info():
    stations_with_previ = models.StationsWithFlowPrevi.objects.values()
    return stations_with_previ