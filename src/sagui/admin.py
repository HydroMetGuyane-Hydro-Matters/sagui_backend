from django.contrib import admin
from django.contrib.gis import admin as geoadmin
from . import models

@admin.register(models.DrainageInclusionMask)
class DrainageInclusionMaskAdmin(geoadmin.GISModelAdmin):
    pass


# admin.site.register(models.Drainage, ordering=['mini'])


@admin.register(models.Stations)
class StationsAdmin(geoadmin.GISModelAdmin):
    pass