-- name: get-team-invitations
SELECT ti.id, ti.team_id, ti.email, ti.role, ti.is_accepted, 
       ti.invited_by_id, ti.invited_by_email, ti.created_at, ti.updated_at
FROM team_invitation ti
WHERE ti.team_id = :team_id
ORDER BY ti.created_at DESC;

-- name: create-team-invitation
INSERT INTO team_invitation (id, team_id, email, role, is_accepted, invited_by_id, invited_by_email, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    :team_id,
    :email,
    :role,
    :is_accepted,
    :invited_by_id,
    :invited_by_email,
    NOW(),
    NOW()
)
RETURNING id, team_id, email, role, is_accepted, invited_by_id, invited_by_email, created_at, updated_at;

-- name: accept-team-invitation
UPDATE team_invitation
SET is_accepted = true,
    updated_at = NOW()
WHERE id = :invitation_id
RETURNING id, team_id, email, role, is_accepted, invited_by_id, invited_by_email, created_at, updated_at;

-- name: get-team-invitation-by-id
SELECT id, team_id, email, role, is_accepted, invited_by_id, invited_by_email, created_at, updated_at
FROM team_invitation
WHERE id = :invitation_id;

-- name: get-pending-invitations-for-email
SELECT id, team_id, email, role, is_accepted, invited_by_id, invited_by_email, created_at, updated_at
FROM team_invitation
WHERE email = :email AND is_accepted = false
ORDER BY created_at DESC;

-- name: delete-team-invitation
DELETE FROM team_invitation
WHERE id = :invitation_id
RETURNING id, team_id, email, role, is_accepted, invited_by_id, invited_by_email, created_at, updated_at;