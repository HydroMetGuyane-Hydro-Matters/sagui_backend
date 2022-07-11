#!/bin/bash
db_host="${POSTGRES_HOST:-localhost}"
db_port="${POSTGRES_PORT:-5432}"
db_name="${POSTGRES_DB:-sagui}"
db_user="${POSTGRES_USER:-postgres}"

# Unzip shapefiles
tar -zxf shapefiles.tar.gz
# Create intermediate gpkg layer from the shapefiles
ogr2ogr -f GPKG layers.gpkg  virtualgpkg.vrt
# delete the shapefiles folder
rm -rf shapefiles
# The clean_data.vrt file is now ready for use (uses the layers.gpkg as source of data)

# read -p "Press enter to continue ..."


# Publish the geospatial data into the DB
#export PGPASSWORD=sagui

# Drainage data
ogr2ogr -f PGDUMP -lco CREATE_TABLE=OFF -lco DROP_TABLE=OFF -nln guyane.hyfaa_drainage \
    /vsistdout/ clean_data.vrt drainage | psql -h $db_host -p $db_port -d $db_name -U $db_user -f -
# Add constraint on mini, needed by django ORM
# psql -h localhost -p 5432 -d sagui -U postgres -c "ALTER TABLE guyane.hyfaa_drainage ADD CONSTRAINT drainage_unique_mini UNIQUE(mini);"

read -p "Press enter to continue ..."


# Catchment data
ogr2ogr -f PGDUMP -lco FID=id -lco CREATE_TABLE=OFF -lco DROP_TABLE=OFF -nln guyane.hyfaa_catchments \
    /vsistdout/ clean_data.vrt catchments | psql -h $db_host -p $db_port -d $db_name -U $db_user -f -
# Add constraint on mini, needed by django ORM
# psql -h localhost -p 5432 -d sagui -U postgres -c "ALTER TABLE guyane.hyfaa_catchments ADD CONSTRAINT catchments_unique_mini UNIQUE(mini);"

read -p "Press enter to continue ..."


# minibasins data
ogr2ogr -f PGDUMP -lco FID=mini  -lco CREATE_TABLE=OFF -lco DROP_TABLE=OFF -nln guyane.hyfaa_minibasins_data \
    /vsistdout/ clean_data.vrt minibasins_data | psql -h $db_host -p $db_port -d $db_name -U $db_user -f -
# Add constraint on mini, needed by django ORM
# psql -h localhost -p 5432 -d sagui -U postgres -c "ALTER TABLE guyane.hyfaa_minibasins_data ADD CONSTRAINT minibasins_data_unique_mini UNIQUE(mini);"

read -p "Press enter to continue ..."


# Stations data
ogr2ogr -f PGDUMP  -lco CREATE_TABLE=OFF -lco DROP_TABLE=OFF -nln guyane.hyfaa_stations \
    /vsistdout/ clean_data.vrt stations | psql -h $db_host -p $db_port -d $db_name -U $db_user -f -

# Display some information
echo "Records in table hyfaa_drainage"
psql -h $db_host -p $db_port -d $db_name -U $db_user -c "SELECT COUNT(*) FROM guyane.hyfaa_drainage;"
echo "Records in table hyfaa_catchments"
psql -h $db_host -p $db_port -d $db_name -U $db_user -c "SELECT COUNT(*) FROM guyane.hyfaa_catchments;"
echo "Records in table hyfaa_minibasins_data"
psql -h $db_host -p $db_port -d $db_name -U $db_user -c "SELECT COUNT(*) FROM guyane.hyfaa_minibasins_data;"
echo "Records in table hyfaa_stations"
psql -h $db_host -p $db_port -d $db_name -U $db_user -c "SELECT COUNT(*) FROM guyane.hyfaa_stations;"

# Remove temp files
rm layers.gpkg
