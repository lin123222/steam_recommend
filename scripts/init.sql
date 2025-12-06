-- 数据库初始化SQL脚本

-- 创建数据库（如果不存在）
-- CREATE DATABASE filmsense;

-- 使用数据库
-- \c filmsense;

-- 创建扩展（如果需要）
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 设置时区
SET timezone = 'UTC';

-- 创建索引（这些将由Alembic管理，这里仅作为参考）
-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_interactions_user_time 
-- ON user_interactions(user_id, timestamp);

-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_interactions_product 
-- ON user_interactions(product_id);

-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_reviews_user 
-- ON user_reviews(user_id);

-- CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_user_reviews_product 
-- ON user_reviews(product_id);

-- 插入一些初始数据（可选）
-- INSERT INTO game_metadata (product_id, title, genres, developer, publisher, metascore, sentiment, release_date, price)
-- VALUES 
--     (1, 'Sample Game 1', '["Action", "Adventure"]', 'Sample Studio', 'Sample Publisher', 85, 'Very Positive', '2023-01-01', 29.99),
--     (2, 'Sample Game 2', '["RPG", "Fantasy"]', 'Another Studio', 'Big Publisher', 92, 'Overwhelmingly Positive', '2023-02-15', 59.99);

-- 提交事务
COMMIT;
