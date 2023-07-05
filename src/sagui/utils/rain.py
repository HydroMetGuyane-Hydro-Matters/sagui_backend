# Stuff related to rain data

import logging
import numpy as np

from django.db import connection

from sagui import models

logger = logging.getLogger(__name__)


# we will use thresholds 5, 20 and 50mm:
# above 50, it's alert r3, below 5, it's alter n (normal, no alert)
ALERT_LEVELS = [
    (0, 'n'),
    (5, 'r1'),
    (20, 'r2'),
    (50, 'r3'),
]


def alert_code_to_rain_mm(code):
    for l in ALERT_LEVELS:
        if l[1] == code:
            return l[0]


def rain_mm_to_alert_code(mm):
    for l in ALERT_LEVELS:
        if l[0] == mm:
            return l[1]


def get_alert_levels_choices():
   return tuple((f'{i[0]}',f'{i[0]} mm', ) for i in ALERT_LEVELS)


def get_global_alert_info():
    # we will use thresholds 5, 20 and 50mm
    # WE will need them in reversed order (higher level first)
    reversed_alert_levels = ALERT_LEVELS.copy()
    reversed_alert_levels.reverse()

    global_alert_level = None
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT ROUND(MAX((values->0->>'rain')::numeric),1) AS l FROM guyane.rainfall_subbasin_aggregated_geo")
            rec = cursor.fetchone()
            mean_rain = rec[0] if rec else None
            for lev in reversed_alert_levels:
                if mean_rain >= lev[0]:
                    global_alert_level = lev[1]
                    break
    except Exception as error:
        logger.error("Exception while fetching Dashboard data:", error)
        logger.error("Exception TYPE:", type(error))

    # Collect rain stats
    rf = models.RainFall.objects.order_by('-date')[0]
    if rf:
        latest_date = rf.date
    latest_rain_records = models.RainFall.objects.filter(date=latest_date)
    values_array = [r.rain for r in latest_rain_records]
    # Use numpy histogram to sort the values into the given bins (alert levels)
    bins = [l[0] for l in ALERT_LEVELS]
    rain_histo = np.histogram(values_array, bins=bins)
    # Initiate rain_data object
    rain_data = {r[1]: 0 for r in ALERT_LEVELS}
    # and fill it with the data from the histogram
    for idx, x in enumerate(rain_histo[0]):
        rain_data[ALERT_LEVELS[idx][1]] = x

    return {
        'global_alert_level': global_alert_level,
        'histogram' : rain_data,
    }