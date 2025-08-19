-- name: clear-team-tags
DELETE FROM team_tag WHERE team_id = :team_id;

-- name: add-team-tag
INSERT INTO team_tag (id, team_id, tag_id, created_at, updated_at)
VALUES (gen_random_uuid(), :team_id, :tag_id, NOW(), NOW())
ON CONFLICT (team_id, tag_id) DO NOTHING;

-- name: remove-team-tag
DELETE FROM team_tag
WHERE team_id = :team_id AND tag_id = :tag_id;

-- name: get-team-tags
SELECT tag.id, tag.slug, tag.name, tag.description, tag.created_at, tag.updated_at
FROM team_tag tt
JOIN tag ON tt.tag_id = tag.id
WHERE tt.team_id = :team_id
ORDER BY tag.name ASC;

-- name: get-teams-with-tag
SELECT t.id, t.slug, t.name, t.description, t.is_active, t.created_at, t.updated_at
FROM team_tag tt
JOIN team t ON tt.team_id = t.id
WHERE tt.tag_id = :tag_id
ORDER BY t.name ASC;

-- name: upsert-team-tag-by-name
INSERT INTO tag (id, name, slug, description, created_at, updated_at)
VALUES (gen_random_uuid(), :name, :slug, :description, NOW(), NOW())
ON CONFLICT (name) DO NOTHING
RETURNING id;

-- name: get-tag-id-by-name
SELECT id FROM tag WHERE name = :name;
