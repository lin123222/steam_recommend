-- 数据库迁移脚本：添加用户游戏库和用户画像表
-- 创建时间: 2024-12-05
-- 说明: 添加 user_library 和 user_profiles 表以支持游戏库和用户画像功能

-- ============================================
-- 1. 创建用户游戏库表
-- ============================================
CREATE TABLE IF NOT EXISTS user_library (
    library_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    app_id VARCHAR(50) NOT NULL,
    
    -- 收藏和安装状态
    is_favorite BOOLEAN DEFAULT FALSE,
    is_installed BOOLEAN DEFAULT FALSE,
    
    -- 购买信息
    purchase_date DATE,
    purchase_price NUMERIC(10, 2),
    
    -- 游玩数据
    playtime_hours NUMERIC(10, 2) DEFAULT 0.0,
    last_played_at TIMESTAMP WITH TIME ZONE,
    
    -- 成就数据
    achievement_progress INTEGER DEFAULT 0,
    achievements_unlocked INTEGER DEFAULT 0,
    achievements_total INTEGER DEFAULT 0,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- 约束
    CONSTRAINT unique_user_product UNIQUE (user_id, product_id)
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_user_library ON user_library(user_id);
CREATE INDEX IF NOT EXISTS idx_user_favorite ON user_library(user_id, is_favorite);
CREATE INDEX IF NOT EXISTS idx_last_played ON user_library(user_id, last_played_at);

-- 添加注释
COMMENT ON TABLE user_library IS '用户游戏库表';
COMMENT ON COLUMN user_library.library_id IS '库记录ID';
COMMENT ON COLUMN user_library.user_id IS '用户ID';
COMMENT ON COLUMN user_library.product_id IS '产品ID';
COMMENT ON COLUMN user_library.app_id IS 'Steam App ID';
COMMENT ON COLUMN user_library.is_favorite IS '是否收藏';
COMMENT ON COLUMN user_library.is_installed IS '是否已安装';
COMMENT ON COLUMN user_library.playtime_hours IS '游玩时长（小时）';
COMMENT ON COLUMN user_library.achievement_progress IS '成就完成百分比';

-- ============================================
-- 2. 创建用户画像扩展表
-- ============================================
CREATE TABLE IF NOT EXISTS user_profiles (
    profile_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    
    -- 基础信息
    avatar_url VARCHAR(500),
    level INTEGER DEFAULT 1,
    exp INTEGER DEFAULT 0,
    exp_to_next_level INTEGER DEFAULT 1000,
    member_since DATE,
    
    -- Gamer DNA (JSON存储)
    gamer_dna_stats TEXT,
    primary_type VARCHAR(50),
    secondary_type VARCHAR(50),
    
    -- Bento Stats
    total_playtime_hours NUMERIC(10, 2) DEFAULT 0.0,
    games_owned INTEGER DEFAULT 0,
    library_value NUMERIC(10, 2) DEFAULT 0.0,
    achievements_unlocked INTEGER DEFAULT 0,
    perfect_games INTEGER DEFAULT 0,
    avg_session_minutes INTEGER DEFAULT 0,
    
    -- Favorite Genres (JSON存储)
    favorite_genres TEXT,
    
    -- 时间戳
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_user_profile ON user_profiles(user_id);

-- 添加注释
COMMENT ON TABLE user_profiles IS '用户画像扩展表';
COMMENT ON COLUMN user_profiles.profile_id IS '画像ID';
COMMENT ON COLUMN user_profiles.user_id IS '用户ID';
COMMENT ON COLUMN user_profiles.gamer_dna_stats IS 'Gamer DNA 统计数据（JSON）';
COMMENT ON COLUMN user_profiles.primary_type IS '主要玩家类型';
COMMENT ON COLUMN user_profiles.secondary_type IS '次要玩家类型';
COMMENT ON COLUMN user_profiles.total_playtime_hours IS '总游玩时长（小时）';
COMMENT ON COLUMN user_profiles.games_owned IS '拥有游戏数';
COMMENT ON COLUMN user_profiles.library_value IS '游戏库总价值';
COMMENT ON COLUMN user_profiles.perfect_games IS '100%完成的游戏数';

-- ============================================
-- 3. 创建触发器：自动更新 updated_at
-- ============================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 为 user_library 表创建触发器
DROP TRIGGER IF EXISTS update_user_library_updated_at ON user_library;
CREATE TRIGGER update_user_library_updated_at
    BEFORE UPDATE ON user_library
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 为 user_profiles 表创建触发器
DROP TRIGGER IF EXISTS update_user_profiles_updated_at ON user_profiles;
CREATE TRIGGER update_user_profiles_updated_at
    BEFORE UPDATE ON user_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- 4. 插入测试数据（可选）
-- ============================================
-- 为测试用户创建画像
-- INSERT INTO user_profiles (user_id, member_since, gamer_dna_stats, primary_type, secondary_type, favorite_genres)
-- VALUES (1, CURRENT_DATE, 
--         '[{"name":"策略","value":85,"max":100},{"name":"反应","value":72,"max":100},{"name":"探索","value":90,"max":100},{"name":"社交","value":45,"max":100},{"name":"收集","value":68,"max":100},{"name":"竞技","value":78,"max":100}]',
--         '探索者', '策略家', '["RPG","Action","Strategy"]')
-- ON CONFLICT (user_id) DO NOTHING;

-- ============================================
-- 5. 验证
-- ============================================
-- 验证表是否创建成功
SELECT table_name, table_type 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('user_library', 'user_profiles');

-- 验证索引是否创建成功
SELECT indexname, tablename 
FROM pg_indexes 
WHERE schemaname = 'public' 
AND tablename IN ('user_library', 'user_profiles');
