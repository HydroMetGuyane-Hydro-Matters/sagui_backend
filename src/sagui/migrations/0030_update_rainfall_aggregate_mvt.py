# Generated by Django 4.0.5 on 2022-10-18 13:16

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sagui', '0029_update_stations_with_flow_alerts_function'),
    ]

    operations = [
        migrations.RunSQL(
        """
-- MVT function
--
-- Display rainfall data depending on the zoom level (show subbasins or minibasins)
-- DROP FUNCTION guyane.mvt_catchments_with_rain_data;
CREATE OR REPLACE
FUNCTION guyane.mvt_rainfall(
            z integer, x integer, y integer)
RETURNS bytea
AS $$
DECLARE
    tblname text;
    result bytea;
BEGIN
    
    CASE

        WHEN z < 10 THEN
            tblname := 'guyane.rainfall_subbasin_aggregated_geo';
        ELSE
            tblname := 'guyane.rainfall_minibasin_aggregated_geo';
    END CASE;

  EXECUTE format('
    WITH
    bounds AS (
      SELECT ST_TileEnvelope($3, $1, $2) AS geom
    ),
    mvtgeom AS (
      SELECT d.id, d."values", ST_AsMVTGeom(ST_Transform(d.geom, 3857), bounds.geom) AS geom
      FROM %s d, bounds
      WHERE ST_Intersects(d.geom, ST_Transform(bounds.geom, 4326))
    )
    SELECT ST_AsMVT(mvtgeom, ''default'')

    FROM mvtgeom;
    ', tblname)
    USING x, y, z
    INTO result;

    RETURN result;
END;
$$
LANGUAGE 'plpgsql'
STABLE
PARALLEL SAFE;
COMMENT ON FUNCTION guyane.mvt_rainfall(z integer, x integer, y integer) IS 
'Exposes rainfall data. Source of data is adjusted depending on the zoom level';
        """),
    ]