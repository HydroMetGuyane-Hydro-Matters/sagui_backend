from django.contrib import admin
from django.contrib.gis.forms import OpenLayersWidget
from django.contrib.gis import admin as geoadmin
from django.conf import settings
from django import forms
from django.shortcuts import redirect, render
from django.urls import path

from . import models
from .utils import reference_data as reference_data_utils


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
    list_display = [field.name for field in models.Stations._meta.fields ]


@admin.register(models.StationsReferenceFlowPeriod)
class StationsReferenceFlowPeriodAdmin(admin.ModelAdmin):
    list_display = ["period"]


class CsvImportForm(forms.Form):
    csv_file = forms.FileField()


@admin.register(models.AtmoAlertCategories)
class AtmoAlertCategoriesAdmin(admin.ModelAdmin):
    pass


@admin.register(models.StationsReferenceFlow)
class StationsReferenceFlowAdmin(admin.ModelAdmin):
    """
    We tweak this admin class, because we don't want to edit/view single entries,
    but series aggregated on (period, station)
    """
    list_display = [ "period", "station",]
    list_filter = ("period__period", "station__name")

    # disable the add button & change actions
    def has_add_permission(self, request, obj=None):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Get only the first of the year, but since we don't show daily specifics,
        # it looks like the list of priod-ly records
        return qs.filter(day_of_year=1)

    # And we add the support for importing data from a CSV
    # (same code than for the django admin command)
    change_list_template = "sagui/stations_ref_flow_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('import-csv/', self.import_csv),
        ]
        return my_urls + urls

    def import_csv(self, request):
        if request.method == "POST":
            csv_file = request.FILES["csv_file"]
            reference_data_utils.import_csv(csv_file)
            self.message_user(request, "Your csv file has been imported")
            return redirect("..")
        form = CsvImportForm()
        payload = {"form": form}
        return render(
            request, "admin/csv_form.html", payload
        )


@admin.register(models.SaguiConfig)
class SaguiConfigAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        base_add_permission = super(SaguiConfigAdmin, self).has_add_permission(request)
        if base_add_permission:
            # if there's already an entry, do not allow adding
            return not models.SaguiConfig.objects.exists()
        return False


@admin.register(models.AlertSubscriptions)
class AlertSubscriptionsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Subscriber', {
            'fields': ('email', 'language',)
        }),
        ('Stations alerts', {
            'fields': ('stations_forecasts_active', 'stations_flow_active', 'stations_watch')
        }),
        ('Rain alerts', {
            'fields': ('rain_active', 'rain_level', )
        }),
        ('Atmo alerts', {
            'fields': ('atmo_active', 'atmo_level',)
        }),
    )
    filter_horizontal = ['stations_watch']
    pass
