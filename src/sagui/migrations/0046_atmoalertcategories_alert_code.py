# Generated by Django 4.0.5 on 2023-03-23 09:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sagui', '0045_auto_20230321_1046'),
    ]

    operations = [
        migrations.AddField(
            model_name='atmoalertcategories',
            name='alert_code',
            field=models.CharField(blank=True, help_text='Code for the alert', max_length=2, null=True),
        ),
    ]