-- name: authenticate-user
SELECT id, email, name, hashed_password, avatar_url, is_active, is_superuser, is_verified, verified_at, joined_at, created_at, updated_at
FROM user_account
WHERE email = :email AND is_active = true;

-- name: update-last-login
UPDATE user_account
SET updated_at = NOW()
WHERE id = :user_id;

-- name: update-password
UPDATE user_account
SET hashed_password = :hashed_password,
    updated_at = NOW()
WHERE id = :user_id
RETURNING id, email, name, hashed_password, avatar_url, is_active, is_superuser, is_verified, verified_at, joined_at, created_at, updated_at;

-- name: reset-password-with-token
UPDATE user_account
SET hashed_password = :hashed_password,
    is_verified = true,
    verified_at = CASE WHEN verified_at IS NULL THEN NOW()::date ELSE verified_at END,
    updated_at = NOW()
WHERE id = :user_id
RETURNING id, email, name, hashed_password, avatar_url, is_active, is_superuser, is_verified, verified_at, joined_at, created_at, updated_at;

-- name: activate-user
UPDATE user_account
SET is_active = true,
    updated_at = NOW()
WHERE id = :user_id
RETURNING id, email, name, hashed_password, avatar_url, is_active, is_superuser, is_verified, verified_at, joined_at, created_at, updated_at;

-- name: deactivate-user
UPDATE user_account
SET is_active = false,
    updated_at = NOW()
WHERE id = :user_id
RETURNING id, email, name, hashed_password, avatar_url, is_active, is_superuser, is_verified, verified_at, joined_at, created_at, updated_at;

-- name: verify-user-email
UPDATE user_account
SET is_verified = true,
    verified_at = NOW()::date,
    updated_at = NOW()
WHERE id = :user_id
RETURNING id, email, name, hashed_password, avatar_url, is_active, is_superuser, is_verified, verified_at, joined_at, created_at, updated_at;