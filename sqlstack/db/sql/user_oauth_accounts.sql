-- name: get-user-oauth-accounts
SELECT id, user_id, provider, oauth_account_id, oauth_account_email, created_at, updated_at
FROM user_account_oauth
WHERE user_id = :user_id
ORDER BY created_at ASC;

-- name: create-user-oauth-account
INSERT INTO user_account_oauth (id, user_id, provider, access_token, expires_at, refresh_token, oauth_account_id, oauth_account_email, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    :user_id,
    :provider,
    :access_token,
    :expires_at,
    :refresh_token,
    :oauth_account_id,
    :oauth_account_email,
    NOW(),
    NOW()
)
RETURNING id, user_id, provider, oauth_account_id, oauth_account_email, created_at, updated_at;

-- name: get-oauth-account-by-provider-id
SELECT id, user_id, provider, access_token, expires_at, refresh_token, oauth_account_id, oauth_account_email, created_at, updated_at
FROM user_account_oauth
WHERE provider = :provider AND oauth_account_id = :oauth_account_id;

-- name: update-oauth-account-tokens
UPDATE user_account_oauth
SET access_token = :access_token,
    expires_at = :expires_at,
    refresh_token = COALESCE(:refresh_token, refresh_token),
    updated_at = NOW()
WHERE id = :oauth_account_id
RETURNING id, user_id, provider, oauth_account_id, oauth_account_email, created_at, updated_at;

-- name: delete-oauth-account
DELETE FROM user_account_oauth
WHERE id = :oauth_account_id
RETURNING id, user_id, provider, oauth_account_id, oauth_account_email, created_at, updated_at;