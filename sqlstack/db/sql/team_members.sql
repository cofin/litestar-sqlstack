-- name: add-team-owner
INSERT INTO team_member (id, team_id, user_id, role, is_owner, created_at, updated_at)
VALUES (gen_random_uuid(), :team_id, :user_id, 'ADMIN', true, NOW(), NOW())
RETURNING id, team_id, user_id, role, is_owner, created_at, updated_at;

-- name: add-team-member
INSERT INTO team_member (id, team_id, user_id, role, is_owner, created_at, updated_at)
VALUES (gen_random_uuid(), :team_id, :user_id, :role, false, NOW(), NOW())
ON CONFLICT (team_id, user_id) DO UPDATE SET
    role = EXCLUDED.role,
    updated_at = NOW()
RETURNING id, team_id, user_id, role, is_owner, created_at, updated_at;

-- name: remove-team-member
DELETE FROM team_member 
WHERE team_id = :team_id AND user_id = :user_id;

-- name: get-team-members
SELECT tm.id, tm.team_id, tm.user_id, tm.role, tm.is_owner, tm.created_at, tm.updated_at,
       u.name as user_name, u.email as user_email
FROM team_member tm
JOIN user_account u ON tm.user_id = u.id
WHERE tm.team_id = :team_id
ORDER BY tm.is_owner DESC, u.name ASC;

-- name: get-user-team-memberships
SELECT tm.id, tm.team_id, tm.user_id, tm.role, tm.is_owner, tm.created_at, tm.updated_at,
       t.name as team_name, t.slug as team_slug
FROM team_member tm
JOIN team t ON tm.team_id = t.id
WHERE tm.user_id = :user_id
ORDER BY t.name ASC;

-- name: is-team-member
SELECT 1 FROM team_member 
WHERE team_id = :team_id AND user_id = :user_id
LIMIT 1;

-- name: is-team-owner
SELECT 1 FROM team_member 
WHERE team_id = :team_id AND user_id = :user_id AND is_owner = true
LIMIT 1;