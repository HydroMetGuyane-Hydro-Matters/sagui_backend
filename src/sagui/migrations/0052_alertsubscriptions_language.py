# Generated by Django 4.0.5 on 2023-04-25 21:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sagui', '0051_alter_alertsubscriptions_rain_level_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='alertsubscriptions',
            name='language',
            field=models.CharField(choices=[('fr', 'Fr'), ('en', 'En'), ('pt-br', 'Br')], default='fr', help_text='Preferred language for the alerts messages', max_length=5),
        ),
    ]
