-- name: create-tag
INSERT INTO tag (id, slug, name, description, created_at, updated_at)
VALUES (
    :id,
    :slug,
    :name,
    :description,
    NOW(),
    NOW()
)
RETURNING id, slug, name, description, created_at, updated_at;

-- name: get-tag-by-id
SELECT id, slug, name, description, created_at, updated_at
FROM tag
WHERE id = :tag_id;

-- name: get-tag-by-slug
SELECT id, slug, name, description, created_at, updated_at
FROM tag
WHERE slug = :slug;

-- name: get-tag-by-name
SELECT id, slug, name, description, created_at, updated_at
FROM tag
WHERE name = :name;

-- name: update-tag
UPDATE tag
SET name = COALESCE(:name, name),
    slug = COALESCE(:slug, slug),
    description = COALESCE(:description, description),
    updated_at = NOW()
WHERE id = :tag_id
RETURNING id, slug, name, description, created_at, updated_at;

-- name: delete-tag
DELETE FROM tag
WHERE id = :tag_id
RETURNING id, slug, name, description, created_at, updated_at;

-- name: list-tags
SELECT id, slug, name, description, created_at, updated_at
FROM tag
ORDER BY name ASC
LIMIT :limit OFFSET :offset;

-- name: count-tags
SELECT COUNT(*) as total FROM tag;

-- name: tag-exists-by-slug
SELECT 1 FROM tag WHERE slug = :slug LIMIT 1;

-- name: tag-exists-by-name
SELECT 1 FROM tag WHERE name = :name LIMIT 1;

-- name: search-tags
SELECT id, slug, name, description, created_at, updated_at
FROM tag
WHERE name ILIKE '%' || :query || '%'
   OR description ILIKE '%' || :query || '%'
ORDER BY name ASC
LIMIT :limit;

-- name: get-popular-tags
SELECT t.id, t.slug, t.name, t.description, t.created_at, t.updated_at,
       COUNT(tt.team_id) as usage_count
FROM tag t
LEFT JOIN team_tag tt ON tt.tag_id = t.id
GROUP BY t.id, t.slug, t.name, t.description, t.created_at, t.updated_at
HAVING COUNT(tt.team_id) >= :min_usage
ORDER BY usage_count DESC, t.name ASC
LIMIT :limit;

-- name: upsert-tag
INSERT INTO tag (id, slug, name, description, created_at, updated_at)
VALUES (
    :id,
    :slug,
    :name,
    :description,
    NOW(),
    NOW()
)
ON CONFLICT (name) DO UPDATE SET
    slug = EXCLUDED.slug,
    description = EXCLUDED.description,
    updated_at = NOW()
RETURNING id, slug, name, description, created_at, updated_at;
