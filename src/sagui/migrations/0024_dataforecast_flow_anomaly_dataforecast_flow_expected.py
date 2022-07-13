# Generated by Django 4.0.5 on 2022-07-13 09:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sagui', '0023_tileserv_ACLs'),
    ]

    operations = [
        migrations.AddField(
            model_name='dataforecast',
            name='flow_anomaly',
            field=models.FloatField(help_text='Represents the anomaly compared to expected data. Formula is 100 * (anomaly - expected) / expected', null=True),
        ),
        migrations.AddField(
            model_name='dataforecast',
            name='flow_expected',
            field=models.FloatField(help_text='Expected value. Calculated using a floating median, over the flow_median values taken on the day surrounding the current day (+ or - 10 days around), during the previous years. Computed from data taken in assimilated table', null=True),
        ),
    ]
