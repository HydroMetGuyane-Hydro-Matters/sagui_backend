# Generated by Django 4.0.5 on 2022-07-06 06:53

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sagui', '0016_stationswithflowalerts_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='StationsWithFlowPrevi',
            fields=[
                ('stationswithflowalerts_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='sagui.stationswithflowalerts')),
            ],
            options={
                'verbose_name': 'Stations with previ codes (View)',
                'db_table': 'stations_with_flow_previ',
                'ordering': ['id'],
                'managed': False,
            },
            bases=('sagui.stationswithflowalerts',),
        ),
        migrations.RenameField(
            model_name='saguiconfig',
            old_name='stations_alert_use_dataset',
            new_name='use_dataset',
        ),
    ]
