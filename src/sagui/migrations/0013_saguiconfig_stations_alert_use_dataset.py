# Generated by Django 4.0.5 on 2022-07-05 07:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sagui', '0012_hyfaa_triggers_on_state'),
    ]

    operations = [
        migrations.AddField(
            model_name='saguiconfig',
            name='stations_alert_use_dataset',
            field=models.CharField(choices=[('mgbstandard', 'Mgbstandard'), ('assimilated', 'Assimilated')], default='mgbstandard', help_text='To determine the alert level for a given stations, its thresholds must be compared with the current values from one dataset. We can choose here which one to use', max_length=15),
        ),
    ]
