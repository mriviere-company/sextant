-- Disposable database for the integration tests (TEST_DATABASE_URL): they truncate tables.
CREATE DATABASE sextant_test OWNER sextant;
\connect sextant_test
CREATE EXTENSION IF NOT EXISTS vector;
\connect sextant
CREATE EXTENSION IF NOT EXISTS vector;
