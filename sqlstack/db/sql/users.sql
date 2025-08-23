-- name: create-user
INSERT INTO user_account (id, email, name, hashed_password, avatar_url, is_active, is_superuser, is_verified, verified_at, joined_at, created_at, updated_at)
VALUES (
    :id,
    :email,
    :name,
    :hashed_password,
    :avatar_url,
    :is_active,
    :is_superuser,
    :is_verified,
    :verified_at,
    :joined_at,
    NOW(),
    NOW()
)
RETURNING id, email, name, case when hashed_password is not null then true else false end as has_password, avatar_url, is_active, is_superuser, is_verified, verified_at, joined_at, created_at, updated_at;

-- name: get-user-by-id
SELECT id, email, name, hashed_password, avatar_url, is_active, is_superuser, is_verified, verified_at, joined_at, created_at, updated_at
FROM user_account
WHERE id = :user_id;

-- name: get-user-with-relationships
SELECT
    u.id, u.email, u.name, case when u.hashed_password is not null then 1 else 0 end as has_password, u.avatar_url,
    u.is_active, u.is_superuser, u.is_verified, u.verified_at, u.joined_at,
    u.created_at, u.updated_at,
    COALESCE(
        json_agg(
            DISTINCT json_build_object(
                'team_id', tm.team_id,
                'team_name', t.name,
                'role', tm.role,
                'is_owner', tm.is_owner
            )
        ) FILTER (WHERE tm.team_id IS NOT NULL),
        '[]'::json
    ) as teams,
    COALESCE(
        json_agg(
            DISTINCT json_build_object(
                'role_id', r.id,
                'role_slug', r.slug,
                'role_name', r.name,
                'assigned_at', ur.assigned_at
            )
        ) FILTER (WHERE r.id IS NOT NULL),
        '[]'::json
    ) as roles,
    COALESCE(
        json_agg(
            DISTINCT json_build_object(
                'id', uoa.id,
                'provider', uoa.provider,
                'oauth_account_id', uoa.oauth_account_id,
                'oauth_account_email', uoa.oauth_account_email
            )
        ) FILTER (WHERE uoa.id IS NOT NULL),
        '[]'::json
    ) as oauth_accounts
FROM user_account u
LEFT JOIN team_member tm ON u.id = tm.user_id
LEFT JOIN team t ON tm.team_id = t.id
LEFT JOIN user_account_role ur ON u.id = ur.user_id
LEFT JOIN role r ON ur.role_id = r.id
LEFT JOIN user_account_oauth uoa ON u.id = uoa.user_id
WHERE u.id = :user_id
GROUP BY u.id, u.email, u.name, case when u.hashed_password is not null then 1 else 0 end, u.avatar_url,
         u.is_active, u.is_superuser, u.is_verified, u.verified_at, u.joined_at,
         u.created_at, u.updated_at;

-- name: get-user-by-email
SELECT id, email, name, case when hashed_password is not null then 1 else 0 end as has_password, avatar_url, is_active, is_superuser, is_verified, verified_at, joined_at, created_at, updated_at
FROM user_account
WHERE email = :email;

-- name: update-user
UPDATE user_account
SET email = COALESCE(:email, email),
    name = COALESCE(:name, name),
    hashed_password = COALESCE(:hashed_password, hashed_password),
    avatar_url = COALESCE(:avatar_url, avatar_url),
    is_active = COALESCE(:is_active, is_active),
    is_superuser = COALESCE(:is_superuser, is_superuser),
    is_verified = COALESCE(:is_verified, is_verified),
    verified_at = COALESCE(:verified_at, verified_at),
    updated_at = NOW()
WHERE id = :user_id
RETURNING id, email, name, hashed_password, avatar_url, is_active, is_superuser, is_verified, verified_at, joined_at, created_at, updated_at;

-- name: delete-user
DELETE FROM user_account
WHERE id = :user_id
RETURNING id, email, name, hashed_password, avatar_url, is_active, is_superuser, is_verified, verified_at, joined_at, created_at, updated_at;

-- name: list-users
SELECT id, email, name, hashed_password, avatar_url, is_active, is_superuser, is_verified, verified_at, joined_at, created_at, updated_at
FROM user_account
ORDER BY created_at DESC
LIMIT :limit OFFSET :offset;

-- name: count-users
SELECT COUNT(*) as total FROM user_account;

-- name: user-exists-by-email
SELECT 1 FROM user_account WHERE email = :email LIMIT 1;

-- name: search-users-by-name
SELECT id, email, name, avatar_url, is_active, is_superuser, is_verified, verified_at, joined_at, created_at, updated_at
FROM user_account
WHERE name ILIKE '%' || :query || '%'
AND is_active = true
ORDER BY name ASC
LIMIT :limit;

-- name: get-active-users
SELECT id, email, name, avatar_url, is_active, is_superuser, is_verified, verified_at, joined_at, created_at, updated_at
FROM user_account
WHERE is_active = true
AND updated_at >= NOW() - INTERVAL ':days days'
ORDER BY updated_at DESC;

-- name: is-superuser
SELECT is_superuser
FROM user_account
WHERE id = :user_id;

-- name: get-user-statistics
SELECT
    COUNT(*) as total_users,
    COUNT(CASE WHEN is_active = true THEN 1 END) as active_users,
    COUNT(CASE WHEN is_verified = true THEN 1 END) as verified_users,
    COUNT(CASE WHEN is_superuser = true THEN 1 END) as superusers,
    COUNT(CASE WHEN updated_at > NOW() - INTERVAL '30 days' THEN 1 END) as recent_logins
FROM user_account;

-- name: get-user-for-password-update
SELECT id, email, hashed_password, is_active, is_verified
FROM user_account
WHERE id = :user_id;

-- name: update-user-password
UPDATE user_account
SET hashed_password = :password_hash, updated_at = NOW()
WHERE id = :user_id
RETURNING id, email, name, is_superuser, is_active, is_verified, hashed_password, avatar_url, verified_at, joined_at, created_at, updated_at;

-- name: reset-user-password
UPDATE user_account
SET hashed_password = :password_hash, is_verified = true, updated_at = NOW()
WHERE id = :user_id
RETURNING id, email, name, is_superuser, is_active, is_verified, hashed_password, avatar_url, verified_at, joined_at, created_at, updated_at;

-- name: create-oauth-user
INSERT INTO user_account (id, email, name, avatar_url, is_active, is_verified, hashed_password, created_at, updated_at, joined_at)
VALUES (
    :id,
    :email,
    :name,
    :avatar_url,
    :is_active,
    :is_verified,
    NULL,
    NOW(),
    NOW(),
    CURRENT_DATE
)
RETURNING id, email, name, is_superuser, is_active, is_verified, hashed_password, avatar_url, verified_at, joined_at, created_at, updated_at;

-- name: user-has-role
SELECT 1
FROM user_account_role ur
JOIN role r ON ur.role_id = r.id
WHERE ur.user_id = :user_id AND r.name = :role_name
LIMIT 1;

-- name: user-has-role-id
SELECT 1
FROM user_account_role
WHERE user_id = :user_id AND role_id = :role_id
LIMIT 1;
