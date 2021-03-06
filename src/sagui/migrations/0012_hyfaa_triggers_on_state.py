# Generated by Django 4.0.5 on 2022-07-04 15:02

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sagui', '0011_hyfaa_drainage_views'),
    ]

    operations = [
        migrations.RunSQL(
        """
        -- Update the materialized views using triggers

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

        RETURN null;
    END $$;


CREATE TRIGGER publication_post_processing
    AFTER INSERT OR UPDATE ON guyane.sagui_importstate
    FOR EACH ROW
    EXECUTE PROCEDURE guyane.publication_post_processing();

        """),
    ]
