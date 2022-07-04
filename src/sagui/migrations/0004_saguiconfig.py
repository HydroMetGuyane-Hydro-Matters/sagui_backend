# Generated by Django 4.0.5 on 2022-07-01 08:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sagui', '0003_remove_dataassimilated_data_assimilated_unique_cellid_day_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='SaguiConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('max_ordem', models.SmallIntegerField(default=12, help_text='Minibasins will be filtered on this value (keep only minibasins with ordem value >= to this one', verbose_name='Max ordem')),
            ],
            options={
                'verbose_name': 'SAGUI configuration',
            },
        ),
    ]