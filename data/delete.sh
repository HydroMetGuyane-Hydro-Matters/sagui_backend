#!/bin/bash
db_host="${POSTGRES_HOST:-localhost}"
db_port="${POSTGRES_PORT:-5432}"
db_name="${POSTGRES_DB:-sagui}"
db_user="${POSTGRES_USER:-postgres}"

# Delete  the geospatial data from the DB ! be careful !
#export PGPASSWORD=sagui

# Stations data
echo "! warn! This will remove all data from the guyane.hyfaa_stations table"
psql -h $db_host -p $db_port -d $db_name -U $db_user "DELETE FROM guyane.hyfaa_stations; ALTER SEQUENCE guyane.hyfaa_stations_id_seq RESTART WITH 1;"

# Drainage data
echo "! warn! This will remove all data from the guyane.hyfaa_drainage table"
psql -h $db_host -p $db_port -d $db_name -U $db_user -c "DELETE FROM guyane.hyfaa_drainage;"


# Catchment data
echo "! warn! This will remove all data from the guyane.hyfaa_catchments table"
psql -h $db_host -p $db_port -d $db_name -U $db_user -c "DELETE FROM guyane.hyfaa_catchments;"


# minibasins data
echo "! warn! This will remove all data from the guyane.hyfaa_minibasins_data table"
psql -h $db_host -p $db_port -d $db_name -U $db_user "DELETE FROM guyane.hyfaa_minibasins_data;"
