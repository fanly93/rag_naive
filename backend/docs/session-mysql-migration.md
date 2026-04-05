# 会话存储迁移到 MySQL（Phase1-Phase4）

本文档记录“会话从内存字典迁移到 MySQL”的实施过程、当前状态与验证方式。

## 1. 目标

- 将 `SessionService` 从进程内存存储改为 MySQL 持久化。
- 保持既有 API 契约不变：
  - 路径不变（`/api/v1/sessions*`）
  - 字段不变（`id/title/updated_at/is_draft/knowledge_base_id`）
  - 错误码与行为不变（如不存在返回 `404 + 1002`）

## 2. 分阶段实施结果

### Phase1：依赖与配置

已完成：
- `backend/requirements.txt`
  - 新增 `sqlalchemy>=2.0.0`
  - 新增 `pymysql>=1.1.0`
- `backend/app/core/config.py`
  - 新增 MySQL 配置字段：`mysql_host/mysql_port/mysql_user/mysql_password/mysql_database/mysql_charset`
  - 支持变量映射：
    - 优先：`MYSQL_*`
    - 兼容：`host/port/user/password/database`
  - 新增 `mysql_sqlalchemy_url` 供 SQLAlchemy 使用

### Phase2：数据库基础设施与启动初始化

已完成：
- 新增 `backend/app/db/base.py`
- 新增 `backend/app/db/session.py`
  - `engine`、`SessionLocal`
  - `init_mysql()`：连接探测 + 建表
- 新增 `backend/app/models/session_model.py`
  - 会话表：`sessions`
- 新增 `backend/app/models/__init__.py` 与 `backend/app/db/__init__.py`
- `backend/app/main.py`
  - 增加 `lifespan`，服务启动时自动执行 `init_mysql()`

### Phase3：会话服务切换为 MySQL

已完成：
- `backend/app/services/session_service.py`
  - 移除内存字典 `_sessions`
  - 所有会话方法改为 DB 查询/写入：
    - `list_sessions`（按 `updated_at` 降序）
    - `create_session`
    - `delete_session`
    - `get_session`
    - `session_exists`
    - `bind_knowledge_base`（并刷新 `updated_at`）

### Phase4：回归验证与文档收敛

已完成：
- 新增自动化脚本：`backend/scripts/session_mysql_regression.py`
- 本文档作为迁移记录与交付说明

## 3. 数据库对象

- 库：`agentic_rag`
- 表：`sessions`
  - `id`（主键）
  - `title`
  - `updated_at`
  - `is_draft`
  - `knowledge_base_id`（可空）

## 4. 账号与权限

已完成：
- 创建用户：`tanglin@'%'`
- 授权：`agentic_rag.*`（ALL PRIVILEGES）
- 已验证 `tanglin/123456` 可访问 `agentic_rag` 并查询 `sessions`

## 5. 回归方式

在 `backend` 目录执行：

```bash
./.venv/bin/python scripts/session_mysql_regression.py
```

脚本覆盖：
- 创建会话接口
- 会话记录落库
- 绑定知识库写库
- 删除会话后数据库同步删除

## 6. 当前状态

- 会话存储迁移已完成并可用。
- 前端会话相关接口无需改动，可直接联调测试。
