# Generated by Django 4.0.5 on 2023-02-28 15:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sagui', '0042_atmoalertcategories_label_en_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='atmoalertcategories',
            name='label_en',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='atmoalertcategories',
            name='label_fr',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='atmoalertcategories',
            name='label_pt',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]
