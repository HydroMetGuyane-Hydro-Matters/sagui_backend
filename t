[1mdiff --git a/src/sagui/migrations/0015_stations_with_previ_levels_function.py b/src/sagui/migrations/0015_stations_with_previ_levels_function.py[m
[1mindex 152a644..e73f91e 100644[m
[1m--- a/src/sagui/migrations/0015_stations_with_previ_levels_function.py[m
[1m+++ b/src/sagui/migrations/0015_stations_with_previ_levels_function.py[m
[36m@@ -12,6 +12,28 @@[m [mclass Migration(migrations.Migration):[m
     operations = [[m
         migrations.RunSQL([m
             """[m
[32m+[m[41m            [m
[32m+[m[32m-- Get alert level as string, depending on the anomaly level (percentage)[m
[32m+[m[32m--DROP FUNCTION guyane.anomaly_to_alert_level(double precision);[m
[32m+[m[32mCREATE OR REPLACE FUNCTION guyane.anomaly_to_alert_level(flow_anomaly double precision)[m
[32m+[m[32m  RETURNS text[m
[32m+[m[32m  LANGUAGE plpgsql AS[m
[32m+[m[32m$func$[m
[32m+[m[32mBEGIN[m
[32m+[m	[32mRETURN (SELECT[m
[32m+[m			[32mCASE[m
[32m+[m			[32m  WHEN flow_anomaly < -50 THEN 'd3'[m
[32m+[m			[32m  WHEN flow_anomaly < -25 THEN 'd2'[m
[32m+[m			[32m  WHEN flow_anomaly < -10 THEN 'd1'[m
[32m+[m			[32m  WHEN flow_anomaly > 50 THEN 'f3'[m
[32m+[m			[32m  WHEN flow_anomaly > 25 THEN 'f2'[m
[32m+[m			[32m  WHEN flow_anomaly > 10 THEN 'f1'[m
[32m+[m			[32m  ELSE 'n'[m
[32m+[m			[32mEND AS level);[m
[32m+[m[32mEND[m
[32m+[m[32m$func$;[m
[32m+[m[32mCOMMENT ON FUNCTION guyane.anomaly_to_alert_level() IS[m[41m [m
[32m+[m[32m'Get alert level as string, depending on the anomaly level (percentage)';[m
 [m
 DROP FUNCTION IF EXISTS guyane.func_stations_with_flow_previ() CASCADE;[m
 CREATE OR REPLACE FUNCTION guyane.func_stations_with_flow_previ()[m
[36m@@ -32,15 +54,7 @@[m [mBEGIN[m
 	RAISE INFO 'dataset_tbl_name %', dataset_tbl_name;[m
 		[m
 	query1 := 'WITH stations AS (SELECT s.id, s.name, s.river, s.minibasin_id AS minibasin_id, s.geom, d."date", [m
[31m-				CASE[m
[31m-				  WHEN d.flow_anomaly < -50 THEN ''d3''[m
[31m-				  WHEN d.flow_anomaly < -25 THEN ''d2''[m
[31m-				  WHEN d.flow_anomaly < -10 THEN ''d1''[m
[31m-				  WHEN d.flow_anomaly > 50 THEN ''f3''[m
[31m-				  WHEN d.flow_anomaly > 25 THEN ''f2''[m
[31m-				  WHEN d.flow_anomaly > 10 THEN ''f1''[m
[31m-				  ELSE ''n''[m
[31m-				END AS level[m
[32m+[m				[32mguyane.anomaly_to_alert_level(flow_anomaly) AS level[m
 				FROM guyane.hyfaa_stations s INNER JOIN %s d[m
 				ON s.minibasin_id = d.cell_id[m
 				WHERE d."date" > (SELECT MAX("date") FROM %s) - ''15 days''::interval[m
