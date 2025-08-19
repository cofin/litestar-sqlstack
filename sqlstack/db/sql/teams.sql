-- name: create-team
INSERT INTO team (id, name, description, slug, is_active, created_at, updated_at)
VALUES (:id, :name, :description, :slug, COALESCE(:is_active, true), NOW(), NOW())
RETURNING id, name, description, slug, is_active, created_at, updated_at;

-- name: update-team
UPDATE team 
SET name = COALESCE(:name, name),
    description = COALESCE(:description, description),
    slug = COALESCE(:slug, slug),
    is_active = COALESCE(:is_active, is_active),
    updated_at = NOW()
WHERE id = :team_id
RETURNING id, name, description, slug, is_active, created_at, updated_at;

-- name: delete-team
DELETE FROM team WHERE id = :team_id;

-- name: get-team-with-relationships
SELECT 
    t.id, t.name, t.description, t.slug, t.is_active, t.created_at, t.updated_at,
    COALESCE(
        json_agg(
            DISTINCT json_build_object(
                'user_id', tm.user_id,
                'role', tm.role,
                'is_owner', tm.is_owner,
                'user_name', u.name,
                'user_email', u.email
            )
        ) FILTER (WHERE tm.user_id IS NOT NULL),
        '[]'::json
    ) as members,
    COALESCE(
        json_agg(
            DISTINCT json_build_object(
                'tag_id', tag.id,
                'tag_name', tag.name,
                'tag_slug', tag.slug
            )
        ) FILTER (WHERE tag.id IS NOT NULL),
        '[]'::json
    ) as tags
FROM team t
LEFT JOIN team_member tm ON t.id = tm.team_id
LEFT JOIN user_account u ON tm.user_id = u.id
LEFT JOIN team_tag tt ON t.id = tt.team_id
LEFT JOIN tag ON tt.tag_id = tag.id
WHERE t.id = :team_id
GROUP BY t.id, t.name, t.description, t.slug, t.is_active, t.created_at, t.updated_at;

-- name: get-team-id-by-slug
SELECT id FROM team WHERE slug = :slug;

-- name: list-teams-for-user
SELECT t.id
FROM team t
WHERE t.id IN (
    SELECT team_id FROM team_member WHERE user_id = :user_id
)
ORDER BY t.name ASC;

-- name: list-all-teams
SELECT id
FROM team
ORDER BY name ASC;

-- name: search-teams
SELECT id
FROM team
WHERE name ILIKE '%' || :query || '%'
ORDER BY name ASC
LIMIT :limit;

-- name: team-slug-exists
SELECT 1 FROM team WHERE slug = :slug LIMIT 1;

-- name: get-teams-for-user
SELECT t.id, t.slug, t.name, t.description, t.is_active, t.created_at, t.updated_at
FROM team t
JOIN team_member tm ON tm.team_id = t.id
WHERE tm.user_id = :user_id
ORDER BY t.name ASC;