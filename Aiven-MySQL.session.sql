SHOW TABLES;
SELECT * FROM categories;

DESCRIBE order_items;

DESCRIBE orders;

SELECT * FROM orders WHERE id = 1;

SELECT id, order_status
FROM orders
WHERE id = 1;

DESCRIBE orders;