# Generated by Django 4.0.5 on 2022-07-13 10:55

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sagui', '0025_compute_anomaly_on_forecast_too'),
    ]

    operations = [
        migrations.RunSQL(
            """
DROP MATERIALIZED VIEW IF EXISTS guyane.hyfaa_forecast_with_assimilated CASCADE;
CREATE MATERIALIZED VIEW guyane.hyfaa_forecast_with_assimilated
AS
WITH forecast_data AS (
	SELECT 'forecast' AS source, cell_id, "date", ROUND(flow_median) AS flow, ROUND(flow_expected) AS flow_expected, ROUND(flow_anomaly) AS flow_anomaly FROM guyane.hyfaa_data_forecast WHERE "date" > (SELECT MAX("date") FROM guyane.hyfaa_data_assimilated)
),
data_10d AS (
	SELECT 'assimilated' AS source, cell_id, "date", ROUND(flow_median) AS flow, ROUND(flow_expected) AS flow_expected, ROUND(flow_anomaly) AS flow_anomaly FROM guyane.hyfaa_data_assimilated WHERE "date" > (SELECT MAX("date") FROM guyane.hyfaa_data_assimilated)  - '10 days'::interval
)
SELECT * FROM forecast_data UNION SELECT * FROM data_10d
ORDER BY cell_id, "date" DESC;
COMMENT ON MATERIALIZED VIEW guyane.hyfaa_forecast_with_assimilated
    IS 'Fusion latest values from assimilated table and forecast values (+/- 10 days)';

DROP MATERIALIZED VIEW IF EXISTS guyane.hyfaa_forecast_with_mgbstandard CASCADE;
CREATE MATERIALIZED VIEW guyane.hyfaa_forecast_with_mgbstandard
AS
WITH forecast_data AS (
	SELECT 'forecast' AS source, cell_id, "date", ROUND(flow_median) AS flow, ROUND(flow_expected) AS flow_expected, ROUND(flow_anomaly) AS flow_anomaly FROM guyane.hyfaa_data_forecast WHERE "date" > (SELECT MAX("date") FROM guyane.hyfaa_data_mgbstandard)
),
data_10d AS (
	SELECT 'mgbstandard' AS source, cell_id, "date", ROUND(flow_mean) AS flow, ROUND(flow_expected) AS flow_expected, ROUND(flow_anomaly) AS flow_anomaly FROM guyane.hyfaa_data_mgbstandard WHERE "date" > (SELECT MAX("date") FROM guyane.hyfaa_data_mgbstandard)  - '10 days'::interval
)
SELECT * FROM forecast_data UNION SELECT * FROM data_10d
ORDER BY cell_id, "date" DESC;
COMMENT ON MATERIALIZED VIEW guyane.hyfaa_forecast_with_mgbstandard
    IS 'Fusion latest values from mgbstandard table and forecast values (+/- 10 days)';
            """),
        migrations.RunSQL(
            """
-- Create materialized view for MVT, fusioning data from assimilated and forecast data
DROP MATERIALIZED VIEW IF EXISTS guyane.hyfaa_forecast_with_assimilated_aggregate_geo CASCADE;
CREATE MATERIALIZED VIEW guyane.hyfaa_forecast_with_assimilated_aggregate_geo 
AS
     WITH data_agg AS (
        SELECT cell_id, json_agg(
            json_build_object(
                'source', source, 
                'date', "date", 
                'flow', flow, 
                'flow_anomaly', flow_anomaly
            ) ORDER BY "date" DESC) AS "values" 
        FROM guyane.hyfaa_forecast_with_assimilated 
        GROUP BY cell_id
        ORDER BY cell_id
    )
    SELECT d.cell_id, d."values", geo.ordem, 
        round(geo.width::numeric) AS width,
        round(geo.depth::numeric, 2) AS depth,
        st_transform(geo.geom, 4326)::geometry(Geometry,4326) AS geom
    FROM data_agg d,
        guyane.drainage_mgb_masked geo
      WHERE geo.mini = d.cell_id
      ORDER BY d.cell_id;
COMMENT ON MATERIALIZED VIEW guyane.hyfaa_forecast_with_assimilated_aggregate_geo
    IS 'Combine the geometries for the minibasins with the values fusioned from latest values in assimilated table and forecast values (+/- 10 days, stored in a json object)';

            
-- Create materialized view for MVT, fusioning data from mgbstandard and forecast data
DROP MATERIALIZED VIEW IF EXISTS guyane.hyfaa_forecast_with_mgbstandard_aggregate_geo CASCADE;
CREATE MATERIALIZED VIEW guyane.hyfaa_forecast_with_mgbstandard_aggregate_geo 
AS
     WITH data_agg AS (
        SELECT cell_id, json_agg(
            json_build_object(
                'source', source, 
                'date', "date", 
                'flow', flow, 
                'flow_anomaly', flow_anomaly
            ) ORDER BY "date" DESC) AS "values" 
        FROM guyane.hyfaa_forecast_with_mgbstandard
        GROUP BY cell_id
        ORDER BY cell_id
    )
    SELECT d.cell_id, d."values", geo.ordem, 
        round(geo.width::numeric) AS width,
        round(geo.depth::numeric, 2) AS depth,
        st_transform(geo.geom, 4326)::geometry(Geometry,4326) AS geom
    FROM data_agg d,
        guyane.drainage_mgb_masked geo
      WHERE geo.mini = d.cell_id
      ORDER BY d.cell_id;
COMMENT ON MATERIALIZED VIEW guyane.hyfaa_forecast_with_mgbstandard_aggregate_geo
    IS 'Combine the geometries for the minibasins with the values fusioned from latest values in mgbstandard table and forecast values (+/- 10 days, stored in a json object)';
            """),
        migrations.RunSQL(
        """
DROP FUNCTION IF EXISTS guyane.func_hyfaa_data_aggregated_geo() CASCADE;
CREATE OR REPLACE FUNCTION guyane.func_hyfaa_data_aggregated_geo()
RETURNS TABLE(cell_id smallint,
                val json,
                ordem bigint,
                width numeric,
                depth numeric,
			    geom geometry(LineString,4326)
			    )
AS $$
DECLARE
	dataset_tbl_name TEXT;
	query1 TEXT;
BEGIN
	-- get the name of the materialized view to use
	SELECT 'guyane.hyfaa_data_with_' || COALESCE((SELECT use_dataset FROM guyane.sagui_saguiconfig LIMIT 1), 'assimilated') || '_aggregate_geo' AS use_dataset
	INTO dataset_tbl_name;
	--RAISE INFO 'dataset_tbl_name %', dataset_tbl_name;
		
	RETURN QUERY EXECUTE format('SELECT * FROM %s', dataset_tbl_name);
END
$$ LANGUAGE plpgsql;
COMMENT ON FUNCTION guyane.func_hyfaa_data_aggregated_geo() IS 
'Provide aggregated data as avialable on materialized view, but use the source data as defined in saguiconfig table.';

CREATE OR REPLACE VIEW guyane.hyfaa_data_aggregated_geo AS
SELECT cell_id, val as "values", width, depth, geom::geometry(Geometry,4326) AS geom FROM guyane.func_hyfaa_data_aggregated_geo();   
COMMENT ON VIEW guyane.hyfaa_data_aggregated_geo IS
'Use this one for MVT display of hyfaa drainage data.
This is a view proxy, serving data from either hyfaa_data_with_assimilated_aggregate_geo or hyfaa_data_with_mgbstandard_aggregate_geo
depending on the dataset selected in saguiconfig table.';


DROP FUNCTION IF EXISTS guyane.func_hyfaa_forecast_aggregated_geo() CASCADE;
CREATE OR REPLACE FUNCTION guyane.func_hyfaa_forecast_aggregated_geo()
RETURNS TABLE(cell_id smallint,
                val json,
                ordem bigint,
                width numeric,
                depth numeric,
			    geom geometry(LineString,4326)
			    )
AS $$
DECLARE
	dataset_tbl_name TEXT;
	query1 TEXT;
BEGIN
	-- get the name of the materialized view to use
	SELECT 'guyane.hyfaa_forecast_with_' || COALESCE((SELECT use_dataset FROM guyane.sagui_saguiconfig LIMIT 1), 'assimilated') || '_aggregate_geo' AS use_dataset
	INTO dataset_tbl_name;
	--RAISE INFO 'dataset_tbl_name %', dataset_tbl_name;
		
	RETURN QUERY EXECUTE format('SELECT * FROM %s', dataset_tbl_name);
END
$$ LANGUAGE plpgsql;
COMMENT ON FUNCTION guyane.func_hyfaa_forecast_aggregated_geo() IS 
'Provide aggregated data as available on materialized view, but use the source data as defined in saguiconfig table.';

CREATE OR REPLACE VIEW guyane.hyfaa_forecast_aggregated_geo AS
SELECT cell_id, val as "values", width, depth, geom::geometry(Geometry,4326) AS geom  FROM guyane.func_hyfaa_forecast_aggregated_geo();   
COMMENT ON VIEW guyane.hyfaa_forecast_aggregated_geo IS
'Use this one for MVT display of forecast drainage data.
This is a view proxy, serving data from either hyfaa_forecast_with_assimilated_aggregate_geo or hyfaa_forecast_with_mgbstandard_aggregate_geo
depending on the dataset selected in saguiconfig table.';

GRANT SELECT ON TABLE guyane.sagui_saguiconfig TO tileserv;
GRANT SELECT ON TABLE guyane.hyfaa_forecast_with_assimilated_aggregate_geo TO tileserv;
GRANT SELECT ON TABLE guyane.hyfaa_forecast_with_mgbstandard_aggregate_geo TO tileserv;
GRANT SELECT ON TABLE guyane.hyfaa_data_aggregated_geo TO tileserv;
GRANT SELECT ON TABLE guyane.hyfaa_forecast_aggregated_geo TO tileserv;
        """),
    ]
