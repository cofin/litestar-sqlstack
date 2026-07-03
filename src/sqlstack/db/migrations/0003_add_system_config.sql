-- SQLSpec Migration
-- Version: 0003
-- Description: Add system_config table for dynamic settings
-- Created: 2026-07-03T20:48:00+00:00
-- Author: executor

-- name: migrate-0003-up
-- dialect: postgres

CREATE TABLE system_config (
    id uuid NOT NULL CONSTRAINT pk_system_config PRIMARY KEY DEFAULT gen_random_uuid(),
    key varchar(255) NOT NULL CONSTRAINT uq_system_config_key UNIQUE,
    value varchar NOT NULL,
    description varchar,
    created_at timestamp with time zone NOT NULL DEFAULT current_timestamp,
    updated_at timestamp with time zone NOT NULL DEFAULT current_timestamp
);

COMMENT ON TABLE system_config IS 'System configuration settings';
COMMENT ON COLUMN system_config.key IS 'Configuration setting key';
COMMENT ON COLUMN system_config.value IS 'Configuration setting value';
COMMENT ON COLUMN system_config.description IS 'Optional description of the configuration setting';

-- name: migrate-0003-down
-- dialect: postgres

DROP TABLE IF EXISTS system_config CASCADE;
