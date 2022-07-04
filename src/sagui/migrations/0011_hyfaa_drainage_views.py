# Generated by Django 4.0.5 on 2022-07-04 14:42

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sagui', '0010_hyfaa_views'),
    ]

    operations = [
        migrations.RunSQL(
            """
CREATE OR REPLACE VIEW guyane.hyfaa_drainage_with_attributes AS
WITH 
ordem AS (SELECT COALESCE(
	(SELECT max_ordem FROM guyane.sagui_saguiconfig LIMIT 1)
	, 12) AS max_ordem)
SELECT d.geom, m.* FROM guyane.hyfaa_drainage d JOIN guyane.hyfaa_minibasins_data m ON d.mini = m.mini
WHERE m.ordem >= (SELECT max_ordem FROM ordem LIMIT 1);

COMMENT ON VIEW guyane.hyfaa_drainage_with_attributes IS 'Drainage linear geometries with minibasins attributes (ordem, width etc)';

-----------------------------------------------------
-- Apply the mask (area to include, if exists) over the drainage table
-----------------------------------------------------
DROP VIEW IF EXISTS guyane.drainage_mgb_masked CASCADE;
CREATE OR REPLACE VIEW guyane.drainage_mgb_masked
 AS
WITH 
geo AS (SELECT ST_UNION(mask) AS mask FROM guyane.hyfaa_geo_inclusion_mask ),
inclusion_mask AS (
	SELECT CASE 
	  WHEN (SELECT count(*) FROM guyane.hyfaa_geo_inclusion_mask) = 0 THEN ST_PolygonFromText('POLYGON((-180 -90, -180 90, 180 90, 180 -90, -180 -90))', 4326)
	  ELSE (SELECT mask FROM geo )
	END AS mask
	FROM geo
)
SELECT dr.*
   FROM guyane.hyfaa_drainage_with_attributes dr,
    inclusion_mask AS mask
  WHERE st_intersects(dr.geom, mask.mask);

COMMENT ON  VIEW guyane.drainage_mgb_masked IS 'Drainage minibasins on Guyane Watershed Basins, as defined by MGB model. With a geographical mask applied to remove out-of-scope area.';


-----------------------------------------------------
-- Join the hyfaa *_aggregate_json views with the geo data.
-- Make them a Materialized View, in order to reduce load
-----------------------------------------------------

-- on assimilated data
DROP MATERIALIZED VIEW IF EXISTS guyane.hyfaa_data_with_assim_aggregate_geo CASCADE;
CREATE MATERIALIZED VIEW guyane.hyfaa_data_with_assim_aggregate_geo
AS
 SELECT data.*,
        geo.ordem,
        ROUND(geo.width::numeric) AS width,
        ROUND(geo.depth::numeric, 2) AS depth,
        ST_Transform(geo.geom, 4326)::geometry(Geometry,4326) AS geom
  FROM guyane.hyfaa_data_assimilated_aggregate_json AS data,
       guyane.drainage_mgb_masked AS geo
  WHERE geo.mini = data.cell_id
  ORDER BY cell_id
WITH DATA;
CREATE UNIQUE INDEX ON guyane.hyfaa_data_with_assim_aggregate_geo (cell_id);

ALTER TABLE guyane.hyfaa_data_with_assim_aggregate_geo
    OWNER TO postgres;

COMMENT ON MATERIALIZED VIEW guyane.hyfaa_data_with_assim_aggregate_geo
    IS 'Combine the geometries for the minibasins with the most recent values (n last days, stored in a json object)';


-- on mgbstandard data
DROP MATERIALIZED VIEW IF EXISTS guyane.hyfaa_data_with_mgbstandard_aggregate_geo CASCADE;
CREATE MATERIALIZED VIEW guyane.hyfaa_data_with_mgbstandard_aggregate_geo
AS
 SELECT data.*,
        geo.ordem,
        ROUND(geo.width::numeric) AS width,
        ROUND(geo.depth::numeric, 2) AS depth,
        ST_Transform(geo.geom, 4326)::geometry(Geometry,4326) AS geom
  FROM guyane.hyfaa_data_mgbstandard_aggregate_json AS data,
       guyane.drainage_mgb_masked AS geo
  WHERE geo.mini = data.cell_id
  ORDER BY cell_id
WITH DATA;
CREATE UNIQUE INDEX ON guyane.hyfaa_data_with_mgbstandard_aggregate_geo (cell_id);

ALTER TABLE guyane.hyfaa_data_with_mgbstandard_aggregate_geo
    OWNER TO postgres;

COMMENT ON MATERIALIZED VIEW guyane.hyfaa_data_with_mgbstandard_aggregate_geo
    IS 'Combine the geometries for the minibasins with the most recent values (n last days, stored in a json object)';


-----------------------------------------------------
-- Create a simple view that abstracts which data source
-- we will use for the visualization. For now, we will
-- use mgbstandard
-----------------------------------------------------
CREATE OR REPLACE VIEW  guyane.hyfaa_data_aggregated_geo AS
    SELECT * FROM guyane.hyfaa_data_with_mgbstandard_aggregate_geo;

            """),
    ]