

SELECT DATABASE();

SELECT COUNT(*) AS total_users FROM users;

DESCRIBE users;


SELECT id, full_name, email, is_admin
FROM users;

SELECT id, full_name, email, is_admin
FROM users
WHERE id = 3;