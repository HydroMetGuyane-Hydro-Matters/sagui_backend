from django.contrib import admin
from django.contrib.gis.forms import OpenLayersWidget
from django.contrib.gis import admin as geoadmin
from . import models


class MyOSMWidget(OpenLayersWidget):
    """
    An OpenLayers/OpenStreetMap-based widget.
    """
    template_name = "gis/admin/openlayers-osm-custom.html"
    default_lon = -53
    default_lat = 4
    default_zoom = 7
    drainage_url = 'http://localhost:7800/tiles/geospatial.drainage/{z}/{x}/{y}.pbf'

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