-- name: get-user-roles
SELECT r.id, r.slug, r.name, r.description, r.created_at, r.updated_at, ur.assigned_at
FROM role r
JOIN user_account_role ur ON ur.role_id = r.id
WHERE ur.user_id = :user_id
ORDER BY r.name ASC;

-- name: assign-role-to-user
INSERT INTO user_account_role (id, user_id, role_id, assigned_at, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    :user_id,
    :role_id,
    NOW(),
    NOW(),
    NOW()
)
ON CONFLICT (user_id, role_id) DO NOTHING;

-- name: remove-role-from-user
DELETE FROM user_account_role
WHERE user_id = :user_id AND role_id = :role_id;

-- name: has-user-role-by-name
SELECT 1
FROM user_account_role ur
JOIN role r ON ur.role_id = r.id
WHERE ur.user_id = :user_id AND r.name = :role_name
LIMIT 1;

-- name: has-user-role-by-id
SELECT 1
FROM user_account_role ur
WHERE ur.user_id = :user_id AND ur.role_id = :role_id
LIMIT 1;