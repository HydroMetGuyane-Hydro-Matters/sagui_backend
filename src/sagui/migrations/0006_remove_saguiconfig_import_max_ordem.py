# Generated by Django 4.0.5 on 2022-07-01 12:55

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sagui', '0005_minibasinsdata_saguiconfig_import_max_ordem_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='saguiconfig',
            name='import_max_ordem',
        ),
    ]
