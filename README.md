# FilmSense Steam游戏推荐系统 - 后端服务

基于深度学习的Steam游戏推荐系统，提供毫秒级延迟的个性化推荐服务。

## 🚀 快速开始

### 使用Docker Compose (推荐)

```bash
# 1. 克隆项目
git clone <repository_url>
cd filmsense-backend

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，修改必要的配置

# 3. 启动所有服务
docker-compose up -d

# 4. 查看服务状态
docker-compose ps

# 5. 查看日志
docker-compose logs -f backend
```

### 本地开发

```bash
# 1. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动数据库和Redis
docker-compose up -d db redis

# 4. 运行数据库迁移
alembic upgrade head

# 5. 启动开发服务器
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

## 📁 项目结构

```
filmsense-backend/
├── backend/                 # 主要应用代码
│   ├── auth/               # 用户认证模块
│   ├── database/           # 数据库模型和连接
│   ├── cache/              # Redis缓存层
│   ├── recall/             # 召回层实现
│   │   ├── base_recall.py      # 召回基类
│   │   ├── popularity_recall.py # 流行度召回
│   │   └── embedding_recall.py  # 嵌入召回
│   ├── ranking/            # 排序层实现
│   │   ├── base_ranker.py      # 排序基类
│   │   ├── rule_ranker.py      # 规则排序
│   │   ├── business_filter.py  # 业务过滤
│   │   ├── diversity_controller.py # 多样性控制
│   │   └── ranking_strategy.py # 排序策略管理
│   ├── api/                # API接口
│   ├── ml_inference/       # ML推理服务
│   ├── events/             # 事件处理
│   ├── game_service/       # 游戏服务
│   ├── monitoring/         # 监控和日志
│   └── main.py             # FastAPI应用入口
├── tests/                  # 测试代码
├── scripts/                # 脚本工具
├── triton_models/          # Triton模型文件
├── alembic/                # 数据库迁移
├── requirements.txt        # Python依赖
├── docker-compose.yml      # Docker编排
└── README.md
```

## 🔧 API文档

启动服务后，访问以下地址查看API文档：

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🧪 测试

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/test_api.py

# 运行测试并生成覆盖率报告
pytest --cov=backend tests/
```

## 📊 性能指标

- P90延迟: < 100ms
- 推荐准确性: 基于用户行为序列
- 支持冷启动: 新用户和新游戏
- 缓存命中率: > 80%

## 🔍 监控

系统提供以下监控指标：

- API延迟（P50, P90, P99）
- 请求成功率
- 召回/排序耗时
- 缓存命中率
- 数据库连接数

## 🚀 部署

### 生产环境部署

```bash
# 使用Gunicorn启动
gunicorn backend.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# 或使用Docker
docker-compose -f docker-compose.prod.yml up -d
```

## 📝 开发规范

- 遵循PEP 8代码风格
- 使用Black格式化代码
- 使用type hints
- 编写单元测试
- 提交前运行测试

## 🤝 贡献指南

1. Fork项目
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建Pull Request

## 📄 许可证

本项目采用MIT许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。
