# Generated by Django 4.0.5 on 2023-01-09 08:33

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sagui', '0034_remove_stationsreferenceflow_stations_re_station_22f930_idx_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='stationsreferenceflow',
            old_name='value',
            new_name='flow',
        ),
    ]
