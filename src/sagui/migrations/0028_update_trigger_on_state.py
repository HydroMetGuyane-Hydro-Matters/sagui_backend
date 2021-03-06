# Generated by Django 4.0.5 on 2022-07-13 14:32

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sagui', '0027_forecast_fix_stations_views'),
    ]

    operations = [
        migrations.RunSQL(
            """
-- Update trigger on importstate table
--
-- Post processing trigger
CREATE OR REPLACE FUNCTION guyane.publication_post_processing()
    RETURNS TRIGGER LANGUAGE plpgsql
    SECURITY DEFINER
    AS $$
    BEGIN
        -- mgbstandard data
        IF NEW."tablename" LIKE '%data_mgbstandard' THEN
            RAISE INFO 'Triggering post-processing on mgbstandard table. Please wait...';
            PERFORM guyane.compute_expected_and_anomaly('guyane.hyfaa_data_mgbstandard', 'flow_mean', 10);
            REFRESH  MATERIALIZED VIEW guyane.hyfaa_data_with_mgbstandard_aggregate_geo;
        END IF;

        -- assimilated data
        IF NEW."tablename" LIKE '%data_assimilated' THEN
            RAISE INFO 'Triggering post-processing on assimilated table. Please wait...';
            PERFORM guyane.compute_expected_and_anomaly('guyane.hyfaa_data_assimilated', 'flow_median', 10);
            REFRESH  MATERIALIZED VIEW guyane.hyfaa_data_with_assimilated_aggregate_geo;
        END IF;

        -- forecast data
        IF NEW."tablename" LIKE '%data_forecast' THEN
            RAISE INFO 'Triggering post-processing on forecast table. Please wait...';
            PERFORM guyane.update_forecast(10);
            REFRESH  MATERIALIZED VIEW guyane.hyfaa_forecast_with_assimilated;
            REFRESH  MATERIALIZED VIEW guyane.hyfaa_forecast_with_mgbstandard;
            REFRESH  MATERIALIZED VIEW guyane.hyfaa_forecast_with_assimilated_aggregate_geo;
            REFRESH  MATERIALIZED VIEW guyane.hyfaa_forecast_with_mgbstandard_aggregate_geo;
        END IF;

        -- rainfall data
        IF NEW."tablename" LIKE '%_rainfall' THEN
            RAISE INFO 'Triggering post-processing on rainfall table. Please wait...';
            REFRESH  MATERIALIZED VIEW guyane.rainfall_subbasin_aggregated_geo;
            REFRESH  MATERIALIZED VIEW guyane.rainfall_minibasin_aggregated_geo;
        END IF;

        RETURN null;
    END $$;

            """),
    ]
