# Generated by Django 4.0.5 on 2023-04-25 08:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sagui', '0047_alertsubscriptions'),
    ]

    operations = [
        migrations.AddField(
            model_name='alertsubscriptions',
            name='stations_watch',
            field=models.ManyToManyField(help_text='Stations to watch', to='sagui.stations'),
        ),
    ]