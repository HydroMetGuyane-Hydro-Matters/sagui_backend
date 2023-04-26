from time import perf_counter

from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.utils import translation
from django.template.loader import get_template

from sagui import models, utils as sagui_utils

class Command(BaseCommand):
    help = '''
    Send relevant alerts (flow, rain, atmo) to subscribed users
    '''

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **kwargs):
        user_language = 'fr'
        translation.activate(user_language)
        tic = perf_counter()
        stations_alert_info = sagui_utils.stations_alert.get_stations_alert_info()
        stations_forecast_info = sagui_utils.stations_forecast.get_stations_alert_info()
        rain_info = sagui_utils.rain.get_global_alert_info()
        atmo_info = sagui_utils.atmo.get_global_alert_info()

        subscriptions = models.AlertSubscriptions.objects.all()
        for sub in subscriptions:
            with translation.override(sub.language):
                self.stdout.write(f'Processing alerts for subscribee {sub.email}')
                alerts = {
                    'stations_flow':None,
                    'stations_forecast':None,
                    'rain':None,
                    'atmo':None,
                }
                stations_on_watch = sub.stations_watch.all()
                station_ids = list(s.id for s in stations_on_watch)
                station_names = list(s.name for s in stations_on_watch)
                if sub.stations_flow_active:
                    alerts['stations_flow'] = list(s for s in stations_alert_info
                                                   if s['id'] in station_ids and s['alert_level'] != 'n')
                if sub.stations_forecasts_active:
                    stations_forecast_on_alert = list()
                    for s in stations_forecast_info:
                        if s['id'] in station_ids:
                            # We take the forecast data, J+5
                            forecast_levels = [lev for lev in s['levels'] if lev['source'] == 'forecast']
                            # J+5 since the list is reversed order by date
                            forecast = forecast_levels[-5]
                            if forecast['level'] != 'n' :
                                stations_forecast_on_alert.append({ 'id': s['id'], 'name': s['name'], 'forecast': forecast, })
                    alerts['stations_forecast'] = stations_forecast_on_alert
                if sub.rain_active and rain_info['global_alert_level']:
                    if sagui_utils.rain.alert_code_to_rain_mm(rain_info['global_alert_level']) >= int(sub.rain_level):
                        alerts['rain'] = { 'global_alert_level' : 'rain_'+rain_info['global_alert_level']}
                if sub.atmo_active and atmo_info['global_alert_level']:
                    if atmo_info['global_alert_level'][1] >= sub.atmo_level.alert_code[1]:
                        alerts['atmo'] = { 'global_alert_level' : 'atmo_'+atmo_info['global_alert_level']}
                tpl = get_template("sagui/alert_email.txt")
                txt_email = tpl.render(context={'sub':sub,
                                                 'alerts':alerts,
                                                 'rain_levels':sagui_utils.rain.ALERT_LEVELS
                                                 }
                                        )
                tpl = get_template("sagui/alert_email.html")
                html_email = tpl.render(context={'sub':sub,
                                                 'alerts':alerts,
                                                 'rain_levels':sagui_utils.rain.ALERT_LEVELS
                                                 }
                                        )
                send_mail(
                    'SAGUI alert',
                    txt_email,
                    'ige31.jp@gmail.com',
                    [sub.email],
                    fail_silently=False,
                    html_message=html_email
                )

        tac = perf_counter()
        self.stdout.write(self.style.SUCCESS('Total processing time: {} s'.format( round(tac - tic), 2 )))
