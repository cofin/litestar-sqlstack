-- name: create-role
INSERT INTO role (id, slug, name, description, created_at, updated_at)
VALUES (
    :id,
    :slug,
    :name,
    :description,
    NOW(),
    NOW()
)
RETURNING id, slug, name, description, created_at, updated_at;

-- name: get-role-by-id
SELECT id, slug, name, description, created_at, updated_at
FROM role
WHERE id = :role_id;

-- name: get-role-by-name
SELECT id, slug, name, description, created_at, updated_at
FROM role
WHERE name = :name;

-- name: get-role-by-slug
SELECT id, slug, name, description, created_at, updated_at
FROM role
WHERE slug = :slug;

-- name: update-role
UPDATE role
SET name = COALESCE(:name, name),
    description = COALESCE(:description, description),
    updated_at = NOW()
WHERE id = :role_id
RETURNING id, slug, name, description, created_at, updated_at;

-- name: delete-role
DELETE FROM role
WHERE id = :role_id
RETURNING id, slug, name, description, created_at, updated_at;

-- name: list-roles
SELECT id, slug, name, description, created_at, updated_at
FROM role
ORDER BY name ASC
LIMIT :limit OFFSET :offset;

-- name: count-roles
SELECT COUNT(*) as total FROM role;

-- name: role-exists-by-name
SELECT 1 FROM role WHERE name = :name LIMIT 1;

-- name: role-exists-by-slug
SELECT 1 FROM role WHERE slug = :slug LIMIT 1;

-- name: get-default-user-role
SELECT id, slug, name, description, created_at, updated_at
FROM role
WHERE name = 'User'
LIMIT 1;

-- name: get-roles-by-permission
SELECT id, slug, name, description, created_at, updated_at
FROM role
WHERE permissions LIKE '%' || :permission || '%'
ORDER BY name ASC;

-- name: get-active-roles
SELECT id, slug, name, description, created_at, updated_at
FROM role
WHERE is_active = true
AND last_used_at IS NOT NULL
ORDER BY last_used_at DESC
LIMIT :limit;
