from django.contrib import admin
from django.contrib.gis.forms import OpenLayersWidget
from django.contrib.gis import admin as geoadmin
from django.conf import settings

from . import models


class MyOSMWidget(OpenLayersWidget):
    """
    An OpenLayers/OpenStreetMap-based widget.
    """
    template_name = "gis/admin/openlayers-osm-custom.html"
    default_lon = -53
    default_lat = 4
    default_zoom = 7
    drainage_url = settings.SAGUI_SETTINGS.get('DRAINAGE_VT_URL', '')

    def __init__(self, attrs=None):
        super().__init__()
        for key in ("default_lon", "default_lat", "default_zoom", "drainage_url"):
            self.attrs[key] = getattr(self, key)
        if attrs:
            self.attrs.update(attrs)


@admin.register(models.DrainageInclusionMask)
class DrainageInclusionMaskAdmin(geoadmin.GISModelAdmin):
    gis_widget = MyOSMWidget


# admin.site.register(models.Drainage, ordering=['mini'])


@admin.register(models.Stations)
class StationsAdmin(geoadmin.GISModelAdmin):
    gis_widget = MyOSMWidget


@admin.register(models.SaguiConfig)
class SaguiConfigAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        base_add_permission = super(SaguiConfigAdmin, self).has_add_permission(request)
        if base_add_permission:
            # if there's already an entry, do not allow adding
            return not models.SaguiConfig.objects.exists()
        return False