# FilmSense Backend - 快速启动指南

## 🚀 5分钟快速启动

### 方法1: Docker Compose (推荐)

```bash
# 1. 克隆项目
git clone <repository_url>
cd filmsense-backend

# 2. 启动所有服务
docker-compose up -d

# 3. 等待服务启动完成
docker-compose logs -f backend

# 4. 访问API文档
# http://localhost:8000/docs
```

### 方法2: 本地开发

```bash
# 1. 安装Python依赖
pip install -r requirements.txt

# 2. 启动PostgreSQL和Redis
docker-compose up -d db redis

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 4. 运行启动脚本
python scripts/start_dev.py
```

## 📋 快速测试

### 1. 健康检查
```bash
curl http://localhost:8000/health
```

### 2. 用户注册
```bash
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com", 
    "password": "password123"
  }'
```

### 3. 用户登录
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "password123"
  }'
```

### 4. 获取推荐
```bash
curl "http://localhost:8000/api/v1/recommendations?user_id=1&topk=5"
```

### 5. 记录交互
```bash
curl -X POST "http://localhost:8000/api/v1/interactions/interact" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "product_id": 123,
    "play_hours": 2.5
  }'
```

## 🔧 加载示例数据

```bash
# 初始化数据库
python scripts/init_db.py

# 加载示例数据
python scripts/load_sample_data.py
```

## 📊 API端点概览

| 端点 | 方法 | 描述 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/v1/auth/register` | POST | 用户注册 |
| `/api/v1/auth/login` | POST | 用户登录 |
| `/api/v1/recommendations` | GET | 获取推荐 |
| `/api/v1/recommendations/popular` | GET | 热门游戏 |
| `/api/v1/interactions/interact` | POST | 记录交互 |
| `/api/v1/user/profile` | GET | 用户资料 |

## 🐛 故障排除

### 数据库连接失败
```bash
# 检查PostgreSQL是否运行
docker-compose ps db

# 查看数据库日志
docker-compose logs db
```

### Redis连接失败
```bash
# 检查Redis是否运行
docker-compose ps redis

# 查看Redis日志
docker-compose logs redis
```

### 服务启动失败
```bash
# 查看后端服务日志
docker-compose logs backend

# 重启服务
docker-compose restart backend
```

## 🔍 监控和调试

### 查看日志
```bash
# 所有服务日志
docker-compose logs -f

# 特定服务日志
docker-compose logs -f backend
```

### 进入容器调试
```bash
# 进入后端容器
docker-compose exec backend bash

# 进入数据库容器
docker-compose exec db psql -U filmsense -d filmsense
```

### 性能监控
```bash
# 查看缓存统计
curl "http://localhost:8000/api/v1/recommendations/stats"
```

## 📝 下一步

1. 查看完整文档: [README.md](README.md)
2. API文档: http://localhost:8000/docs
3. 配置生产环境: [docker-compose.prod.yml](docker-compose.prod.yml)
4. 运行测试: `pytest tests/`

## 💡 提示

- 首次启动可能需要几分钟来下载Docker镜像
- 确保端口8000、5432、6379未被占用
- 生产环境请修改默认密码和密钥
- 建议使用Python 3.9+版本
