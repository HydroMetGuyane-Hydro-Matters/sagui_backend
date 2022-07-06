from django.urls import path, re_path
from django.views.generic import RedirectView
from rest_framework.urlpatterns import format_suffix_patterns
from . import views

from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    # path('api/v1/sagui', views.api_root),
    path('api/v1/flow_previ/stations', views.StationsPreviList.as_view(), name="flow-previ-get-stations-list"),
    path('api/v1/flow_previ/stations/<int:id>/data', views.StationsPreviRecordsById.as_view(), name="flow-previ-get-stationrecords-by-id"),

    path('api/v1/flow_alerts/stations', views.StationsAlertList.as_view(), name="flow-alerts-get-stations-list"),
    path('api/v1/flow_alerts/stations/<int:id>/data', views.StationFlowRecordsById.as_view(), name="flow-alert-get-stationrecords-by-id"),

    path('api/schema/', SpectacularAPIView.as_view(), name='openapi-schema'),
    # Optional UI:
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='openapi-schema'), name='swagger-ui'),
    # path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('api/v1/', RedirectView.as_view(pattern_name='swagger-ui', permanent=False)),
    path('api/', RedirectView.as_view(pattern_name='swagger-ui', permanent=False)),
]

urlpatterns = format_suffix_patterns(urlpatterns, allowed=['json', 'html', 'geojson'])