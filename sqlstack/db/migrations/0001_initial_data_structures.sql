-- SQLSpec Migration
-- Version: 0001
-- Description: Initial data structures
-- Created: 2025-08-14T20:00:58.967827+00:00
-- Author: cody
-- name: migrate-0001-up 
create table
    role (
        id uuid not null constraint pk_role primary key,
        slug varchar(100) not null constraint uq_role_slug unique,
        name varchar not null constraint uq_role_name unique,
        description varchar,
        created_at timestamp
        with
            time zone not null,
            updated_at timestamp
        with
            time zone not null
    );

alter table role owner to app;

create unique index ix_role_slug_unique on role (slug);

create table
    tag (
        id uuid not null constraint pk_tag primary key,
        slug varchar(100) not null constraint uq_tag_slug unique,
        name varchar not null,
        description varchar(255),
        created_at timestamp
        with
            time zone not null,
            updated_at timestamp
        with
            time zone not null
    );

alter table tag owner to app;

create unique index ix_tag_slug_unique on tag (slug);

create table
    team (
        id uuid not null constraint pk_team primary key,
        slug varchar(100) not null constraint uq_team_slug unique,
        name varchar not null,
        description varchar(500),
        is_active boolean not null,
        created_at timestamp
        with
            time zone not null,
            updated_at timestamp
        with
            time zone not null
    );

alter table team owner to app;

create index ix_team_name on team (name);

create unique index ix_team_slug_unique on team (slug);

create table
    user_account (
        id uuid not null constraint pk_user_account primary key,
        email varchar not null,
        name varchar,
        hashed_password varchar(255),
        avatar_url varchar(500),
        is_active boolean not null,
        is_superuser boolean not null,
        is_verified boolean not null,
        verified_at date,
        joined_at date not null,
        created_at timestamp
        with
            time zone not null,
            updated_at timestamp
        with
            time zone not null
    );

comment on table user_account is 'User accounts for application access';

alter table user_account owner to app;

create unique index ix_user_account_email on user_account (email);

create table
    team_invitation (
        id uuid not null constraint pk_team_invitation primary key,
        team_id uuid not null constraint fk_team_invitation_team_id_team references team on delete cascade,
        email varchar not null,
        role varchar(50) not null,
        is_accepted boolean not null,
        invited_by_id uuid constraint fk_team_invitation_invited_by_id_user_account references user_account on delete set null,
        invited_by_email varchar not null,
        created_at timestamp
        with
            time zone not null,
            updated_at timestamp
        with
            time zone not null
    );

alter table team_invitation owner to app;

create index ix_team_invitation_email on team_invitation (email);

create table
    team_member (
        id uuid not null constraint pk_team_member primary key,
        user_id uuid not null constraint fk_team_member_user_id_user_account references user_account on delete cascade,
        team_id uuid not null constraint fk_team_member_team_id_team references team on delete cascade,
        role varchar(50) not null,
        is_owner boolean not null,
        created_at timestamp
        with
            time zone not null,
            updated_at timestamp
        with
            time zone not null,
            constraint uq_team_member_user_id unique (user_id, team_id)
    );

alter table team_member owner to app;

create index ix_team_member_role on team_member (role);

create table
    team_tag (
        team_id uuid not null constraint fk_team_tag_team_id_team references team on delete cascade,
        tag_id uuid not null constraint fk_team_tag_tag_id_tag references tag on delete cascade,
        constraint pk_team_tag primary key (team_id, tag_id)
    );

alter table team_tag owner to app;

create table
    user_account_oauth (
        id uuid not null constraint pk_user_account_oauth primary key,
        user_id uuid not null constraint fk_user_account_oauth_user_id_user_account references user_account on delete cascade,
        provider varchar(100) not null,
        access_token varchar(1024) not null,
        expires_at integer,
        refresh_token varchar(1024),
        oauth_account_id varchar(320) not null,
        oauth_account_email varchar(320),
        created_at timestamp
        with
            time zone not null,
            updated_at timestamp
        with
            time zone not null
    );

comment on table user_account_oauth is 'Registered OAUTH2 Accounts for Users';

alter table user_account_oauth owner to app;

create index ix_user_account_oauth_oauth_account_id on user_account_oauth (oauth_account_id);

create index ix_user_account_oauth_provider on user_account_oauth (provider);

create table
    user_account_role (
        id uuid not null constraint pk_user_account_role primary key,
        user_id uuid not null constraint fk_user_account_role_user_id_user_account references user_account on delete cascade,
        role_id uuid not null constraint fk_user_account_role_role_id_role references role on delete cascade,
        assigned_at timestamp
        with
            time zone not null,
            created_at timestamp
        with
            time zone not null,
            updated_at timestamp
        with
            time zone not null
    );

comment on table user_account_role is 'Links a user to a specific role.';

alter table user_account_role owner to app;

-- name: migrate-0001-down
DROP TABLE IF EXISTS user_account_role CASCADE;

DROP TABLE IF EXISTS user_account_oauth CASCADE;

DROP TABLE IF EXISTS team_tag CASCADE;

DROP TABLE IF EXISTS team_member CASCADE;

DROP TABLE IF EXISTS team_invitation CASCADE;

DROP TABLE IF EXISTS user_account CASCADE;

DROP TABLE IF EXISTS team CASCADE;

DROP TABLE IF EXISTS tag CASCADE;

DROP TABLE IF EXISTS role CASCADE;