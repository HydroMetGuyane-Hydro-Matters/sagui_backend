-- pg_tileserv user
DROP ROLE IF EXISTS tileserv;
CREATE ROLE tileserv WITH
	LOGIN
	ENCRYPTED PASSWORD 'pg_tileserv'
	CONNECTION LIMIT 50;

GRANT USAGE ON SCHEMA guyane TO tileserv;