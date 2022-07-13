# Generated by Django 4.0.5 on 2022-07-13 10:29

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sagui', '0024_dataforecast_flow_anomaly_dataforecast_flow_expected'),
    ]

    operations = [
        migrations.RunSQL(
        """
-- Computes and inserts values for the flow_expected and flow_anomaly columns
-- flow_expected is calculated using the floating median
-- flow_anomaly is calculated using the above function, and uses the 'expected' value
-- this new version allows to compute the values from data on another table than the
-- one the computed values will be inserted too (use-case: compute anomaly for forecast
-- data, based on historical values from assimilated table)
-- RETURNS the number of updated dates
CREATE OR REPLACE FUNCTION guyane.compute_expected_and_anomaly(
                                                    _dest_tbl regclass,
                                                    _src_tbl regclass,
                                                    _columnname text,
                                                    _nbdays int default 10,
                                                    lower_date date default '1950-01-01'
                                                  )
RETURNS SMALLINT
AS
$$
DECLARE
    TABLE_RECORD RECORD;
	query1 TEXT;
	query2 TEXT;
	counter SMALLINT;
BEGIN
    -- list the dates at which we have some undefined values for 'expected' or 'anomaly' columns
    query1 :='SELECT "date" AS upt_date
                            FROM %s
                            WHERE (flow_expected IS NULL OR flow_anomaly IS NULL)
                            AND "date" > $1::date
                            GROUP BY upt_date
                            ORDER BY upt_date DESC';
    -- is run inside the loop. The subquery 'subq' computes the median value on the determined field (flow_mean or
    -- flow_median, supposedly) on a subsample of dates (see guyane.surrounding_days_over_previous_years function for
    -- definition)
    -- The data from 'subq' is then inserted into the original table, for the given date
    -- ($1, i.e. TABLE_RECORD."upt_date")
    query2 := ' UPDATE %s
                    SET flow_expected = subq.median,
                        flow_anomaly = guyane.compute_anomaly(%s, subq.median)
                    FROM (SELECT cell_id AS id, median(%s)
                        FROM %s AS d
                        WHERE "date" IN (SELECT guyane.surrounding_days_over_previous_years($1, $2) )
                        GROUP BY cell_id) AS subq
                    WHERE "date" = $1
                        AND cell_id = subq.id';
    counter := 0;
    -- Loop over those dates
    FOR TABLE_RECORD IN EXECUTE format(query1, _dest_tbl) USING lower_date
        LOOP
            EXECUTE format(query2, _dest_tbl, _columnname, _columnname, _src_tbl) USING TABLE_RECORD."upt_date", _nbdays;
            RAISE INFO '[%] Computed flow_expected and flow_anomaly for date %', _dest_tbl, TABLE_RECORD."upt_date";
            counter := counter + 1;
        END LOOP;
    RETURN counter;
END
$$  LANGUAGE plpgsql;
COMMENT ON FUNCTION guyane.compute_expected_and_anomaly(_dest_tbl regclass, _src_tbl regclass, _columnname text, _nbdays int, lower_date date)
    IS 'Computes and inserts values for the flow_expected and flow_anomaly columns in _dest_tbl.
    flow_expected is calculated using the floating median from _src_tbl
    flow_anomaly is calculated using the above function, and uses the ''expected'' value
	_dest_tbl and _src_tbl are usually the same, but can be different (e.g. compute values for forecast data using historical data from assimilated data)
    RETURNS the number of updated dates';
        """),
        migrations.RunSQL(
        """
-- update the historical, simpler function to use the more generic one (above)
CREATE OR REPLACE FUNCTION guyane.compute_expected_and_anomaly(
                                                    _tbl regclass,
                                                    _columnname text,
                                                    _nbdays int default 10,
                                                    lower_date date default '1950-01-01'
                                                  )
RETURNS SMALLINT
AS
$$
DECLARE
	counter SMALLINT;
BEGIN
    SELECT guyane.compute_expected_and_anomaly(_tbl, _tbl, _columnname, _nbdays, lower_date) INTO counter;
    RETURN counter;
END
$$  LANGUAGE plpgsql;
COMMENT ON FUNCTION guyane.compute_expected_and_anomaly(_tbl regclass, _columnname text, _nbdays int, lower_date date)
    IS 'Computes and inserts values for the flow_expected and flow_anomaly columns.
    flow_expected is calculated using the floating median
    flow_anomaly is calculated using the above function, and uses the ''expected'' value
    RETURNS the number of updated dates';
        """),
        migrations.RunSQL(
        """
-- dedicated function to the forecast context. Handles a possible change of data table from the saguiconfig table 
-- (does not recompute existing values upon change, but will switch seamlessly. And after 10 days, the transition will
-- be complete)
--DROP FUNCTION guyane.update_forecast(integer,date);
CREATE OR REPLACE FUNCTION guyane.update_forecast(
                                                    _nbdays int default 10,
                                                    lower_date date default '1950-01-01'
                                                  )
RETURNS integer
AS
$$
DECLARE
	counter integer;
	dest_tbl_name regclass;
	src_tbl_name regclass;
	flow_field_name TEXT;
	query1 TEXT;
BEGIN
	dest_tbl_name = 'guyane.hyfaa_data_forecast'::regclass;
	
	-- get the name of the dataset to use to match the thresholds. Can be default (assimilated) or defined in the saguiconfig table
	SELECT ('guyane.hyfaa_data_' || COALESCE((SELECT use_dataset FROM guyane.sagui_saguiconfig LIMIT 1), 'assimilated'))::regclass AS use_dataset
	INTO src_tbl_name;
	--RAISE INFO 'src_tbl_name %', src_tbl_name;
	
	IF src_tbl_name::TEXT = 'guyane.hyfaa_data_assimilated' 
	THEN flow_field_name:='flow_median';
	ELSE flow_field_name:='flow_mean'; --means we use mgbstandard dataset
	END IF;
    --RAISE INFO 'flow_field_name %', flow_field_name;
	
	EXECUTE 'SELECT guyane.compute_expected_and_anomaly($1, $2, $3, $4, $5)'
	INTO counter
	USING dest_tbl_name, src_tbl_name, flow_field_name, _nbdays, lower_date;
	
	-- Remove deprecated data (older that most recent data from assimilated or mgbstandard tables)
	EXECUTE format('DELETE FROM %s WHERE "date" < (SELECT MAX("date") FROM %s);',
						 dest_tbl_name, src_tbl_name);
	
    RETURN counter;
END
$$  LANGUAGE plpgsql;
COMMENT ON FUNCTION guyane.update_forecast(_nbdays int, lower_date date)
    IS 'Computes and inserts values for the flow_expected and flow_anomaly columns, 
	using the data from the table configured in saguiconfig (default is assimilated table, but can also be mgbstandard).
	It also cleans old forecast data (in past time) that won''t be used anymore';
        """),
    ]