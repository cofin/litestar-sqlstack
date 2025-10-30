-- SQLSpec Migration
-- Version: 0001
-- Description: Initial data structures
-- Created: 2025-08-14T20:00:58.967827+00:00
-- Author: cody
-- name: migrate-0001-up
-- dialect: postgres
create table role (
    id uuid not null constraint pk_role primary key,
    slug varchar(100) not null constraint uq_role_slug unique,
    name varchar not null constraint uq_role_name unique,
    description varchar,
    created_at timestamp with time zone not null,
    updated_at timestamp with time zone not null
);
create unique index ix_role_slug_unique on role (slug);
create table tag (
    id uuid not null constraint pk_tag primary key,
    slug varchar(100) not null constraint uq_tag_slug unique,
    name varchar not null,
    description varchar(255),
    created_at timestamp with time zone not null,
    updated_at timestamp with time zone not null
);
create unique index ix_tag_slug_unique on tag (slug);
create table team (
    id uuid not null constraint pk_team primary key,
    slug varchar(100) not null constraint uq_team_slug unique,
    name varchar not null,
    description varchar(500),
    is_active boolean not null,
    is_superuser boolean not null default false,
    created_at timestamp with time zone not null,
    updated_at timestamp with time zone not null
);
create index ix_team_name on team (name);
create unique index ix_team_slug_unique on team (slug);
create table user_account (
    id uuid not null constraint pk_user_account primary key,
    email varchar not null,
    name varchar,
    hashed_password varchar(255),
    avatar_url varchar(500),
    is_active boolean not null,
    is_superuser boolean not null default false,
    is_verified boolean not null,
    verified_at date,
    joined_at date not null,
    created_at timestamp with time zone not null,
    updated_at timestamp with time zone not null
);
comment on table user_account is 'User accounts for application access';
create unique index ix_user_account_email on user_account (email);
create table team_invitation (
    id uuid not null constraint pk_team_invitation primary key,
    team_id uuid not null constraint fk_team_invitation_team_id_team references team on delete cascade,
    email varchar not null,
    role varchar(50) not null,
    is_accepted boolean not null,
    invited_by_id uuid constraint fk_team_invitation_invited_by_id_user_account references user_account on delete
    set null,
        invited_by_email varchar not null,
        created_at timestamp with time zone not null,
        updated_at timestamp with time zone not null
);
create index ix_team_invitation_email on team_invitation (email);
create table team_member (
    id uuid not null constraint pk_team_member primary key,
    user_id uuid not null constraint fk_team_member_user_id_user_account references user_account on delete cascade,
    team_id uuid not null constraint fk_team_member_team_id_team references team on delete cascade,
    role varchar(50) not null,
    is_owner boolean not null,
    joined_at timestamp with time zone not null,
    created_at timestamp with time zone not null,
    updated_at timestamp with time zone not null,
    constraint uq_team_member_user_id unique (user_id, team_id)
);
create index ix_team_member_role on team_member (role);
create table team_tag (
    team_id uuid not null constraint fk_team_tag_team_id_team references team on delete cascade,
    tag_id uuid not null constraint fk_team_tag_tag_id_tag references tag on delete cascade,
    constraint pk_team_tag primary key (team_id, tag_id)
);
create table user_account_role (
    id uuid not null constraint pk_user_account_role primary key,
    user_id uuid not null constraint fk_user_account_role_user_id_user_account references user_account on delete cascade,
    role_id uuid not null constraint fk_user_account_role_role_id_role references role on delete cascade,
    assigned_at timestamp with time zone not null,
    created_at timestamp with time zone not null,
    updated_at timestamp with time zone not null
);
comment on table user_account_role is 'Links a user to a specific role.';
create table email_verification_token (
    id uuid not null constraint pk_email_verification_token primary key,
    user_id uuid not null constraint fk_email_verification_token_user_id_user_account references user_account on delete cascade,
    email varchar not null,
    token varchar(255) not null constraint uq_email_verification_token_token unique,
    expires_at timestamp with time zone not null,
    created_at timestamp with time zone not null,
    updated_at timestamp with time zone not null
);
create index ix_email_verification_token_user_id on email_verification_token (user_id);
create index ix_email_verification_token_token on email_verification_token (token);
create table password_reset_token (
    id uuid not null constraint pk_password_reset_token primary key,
    user_id uuid not null constraint fk_password_reset_token_user_id_user_account references user_account on delete cascade,
    token varchar(255) not null constraint uq_password_reset_token_token unique,
    expires_at timestamp with time zone not null,
    created_at timestamp with time zone not null,
    updated_at timestamp with time zone not null
);
create index ix_password_reset_token_user_id on password_reset_token (user_id);
create index ix_password_reset_token_token on password_reset_token (token);
-- name: migrate-0001-down
DROP TABLE IF EXISTS password_reset_token CASCADE;
DROP TABLE IF EXISTS email_verification_token CASCADE;
DROP TABLE IF EXISTS user_account_role CASCADE;
DROP TABLE IF EXISTS team_tag CASCADE;
DROP TABLE IF EXISTS team_member CASCADE;
DROP TABLE IF EXISTS team_invitation CASCADE;
DROP TABLE IF EXISTS user_account CASCADE;
DROP TABLE IF EXISTS team CASCADE;
DROP TABLE IF EXISTS tag CASCADE;
DROP TABLE IF EXISTS role CASCADE;