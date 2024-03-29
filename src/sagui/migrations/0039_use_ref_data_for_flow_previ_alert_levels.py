# Generated by Django 4.0.5 on 2023-01-11 08:30

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sagui', '0038_atmoalertcategories_color_and_more'),
    ]

    operations = [
        migrations.RunSQL(
            """
DROP FUNCTION IF EXISTS guyane.func_stations_with_flow_previ() CASCADE;
CREATE OR REPLACE FUNCTION guyane.func_stations_with_flow_previ()
RETURNS TABLE(id bigint,
			  name varchar(50), 
			 river varchar(50),
			 minibasin smallint,
		     levels jsonb,
			 geom geometry(Point,4326))
AS $$
DECLARE
	dataset_tbl_name TEXT;
	query1 TEXT;
BEGIN
	-- get the name of the dataset to use to match the thresholds. Can be default (assimilated) or defined in the saguiconfig table
	SELECT 'guyane.hyfaa_forecast_with_' || COALESCE((SELECT use_dataset FROM guyane.sagui_saguiconfig LIMIT 1), 'assimilated') AS use_dataset
	INTO dataset_tbl_name;
	RAISE INFO 'dataset_tbl_name %', dataset_tbl_name;
		
	-- in the following query, I'm keeping a lot of extra fields, this is not optimised on purpose since this calculation might still change in the future
	query1 := 'WITH stations AS (
            SELECT s.id, s.name, s.river, s.minibasin_id AS minibasin_id, s.geom, d."date", d.source, d.flow,d.flow_expected, d.flow_anomaly,
                guyane.anomaly_to_alert_level(flow_anomaly) AS level
            FROM guyane.hyfaa_stations s INNER JOIN %s d
                ON s.minibasin_id = d.cell_id
            ORDER BY s.name, d."date" DESC
        ),
        ref_flow_latest AS (
            SELECT * FROM guyane.stations_reference_flow WHERE period_id IN (SELECT id FROM guyane.stations_reference_flow_period ORDER BY period DESC LIMIT 1)
        ),
        stations_with_refperiod AS (
            SELECT s.*, r.flow AS flow_ref, guyane.compute_anomaly(s.flow, r.flow) AS flow_anomaly_ref,
            guyane.anomaly_to_alert_level(guyane.compute_anomaly(s.flow, r.flow) ) AS level_ref
            FROM stations s LEFT JOIN ref_flow_latest r
                     ON s.id=r.station_id AND DATE_PART(''doy'',s."date") = r.day_of_year
                                           ORDER BY s.name, s."date" DESC
        )
        --     SELECT * FROM stations_with_refperiod
        SELECT id, name, river, minibasin_id, jsonb_agg(jsonb_build_object(
            ''date'',"date",
            ''source'', source,
            ''level'', level_ref
        ) ORDER BY "date" DESC) AS levels, geom
        FROM stations_with_refperiod
        GROUP BY id, name, river, minibasin_id, geom';
	RETURN QUERY EXECUTE format(query1, dataset_tbl_name, dataset_tbl_name);
END
$$ LANGUAGE plpgsql;
COMMENT ON FUNCTION guyane.func_stations_with_flow_previ() IS 
'Append forecast levels on stations data. Levels are based on an anomaly that is computed using the reference flow values from stations_reference_flow, not the flow_expected value';

CREATE VIEW guyane.stations_with_flow_previ AS
SELECT * FROM guyane.func_stations_with_flow_previ();      
            """),
    ]
