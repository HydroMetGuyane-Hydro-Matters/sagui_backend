# Stuff related to stations alert data

from collections import Counter
import logging

from django.db import connection

logger = logging.getLogger(__name__)

# global constants
# FLOW_ALERT_LEVELS = ['f3', 'f2', 'f1', 'd3', 'd2', 'd1', 'n']
FLOW_ALERT_LEVELS = ['d2', 'n', 'f1', 'f2', 'f3']


def get_global_alert_info():
    with connection.cursor() as cursor:
        cursor.execute('SELECT levels->0->>\'level\' AS l FROM guyane.stations_with_flow_alerts')
        recs = cursor.fetchall()

    rec_levels = [r[0] for r in recs] if recs else []
    levels_count = Counter(rec_levels)
    levels_stats = {k: levels_count[k] for k in FLOW_ALERT_LEVELS}
    global_alert_level = None
    for lev in FLOW_ALERT_LEVELS:
        if lev in rec_levels:
            global_alert_level = lev
            break
    return {
        'global_alert_level': global_alert_level,
        'histogram' : levels_stats,
    }
