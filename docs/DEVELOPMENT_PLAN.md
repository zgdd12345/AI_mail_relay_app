# AI Mail Relay 文献管理与用户管理系统开发计划

**创建日期**：2025-12-11
**最后更新**：2025-12-12

## 项目概述

在现有 AI Mail Relay 基础上增加两个核心功能：
1. **文献管理系统**：持久化存储论文，防止重复处理
2. **用户管理系统**：支持多用户订阅（分类 + 关键词）

**技术选型**：SQLite（Python 标准库，无额外依赖）
**管理方式**：CLI 命令（管理员手动添加用户）
**上线策略**：分阶段，向后兼容

## 当前进度

- [x] **阶段一：文献存储与去重**（已完成 ✅ 2025-12-11）
- [x] **阶段二：用户管理系统**（已完成 ✅ 2025-12-12）

**最新进展（阶段二）**
- 已落地多用户数据库表、订阅管理与投递历史（迁移版本 2）
- 新增 CLI：`ai-mail-relay user add/list/show/activate/deactivate/subscribe/unsubscribe/subscriptions`
- Pipeline 支持多用户模式：按用户订阅过滤、跳过已投递论文、个性化发送
- MailSender 支持 per-user 收件人与摘要映射，保持单用户向后兼容

---

## 文档更新任务

实现完成后需要更新以下文档：

### 1. CLAUDE.md 需要添加的内容

在 "Architecture" 部分添加新章节：

```markdown
### Database Layer (NEW)

The application uses SQLite for persistent storage:
- `database/connection.py`: SQLite connection management with WAL mode
- `database/migrations.py`: Schema versioning and migrations
- `repositories/paper_repository.py`: Paper CRUD operations
- `repositories/user_repository.py`: User CRUD operations
- `repositories/subscription_repository.py`: Subscription management
- `services/paper_service.py`: Deduplication logic
- `services/user_service.py`: User subscription matching
- `services/delivery_service.py`: Email delivery tracking

Configuration:
- `DatabaseConfig`: Database path and backup settings
- `MultiUserConfig`: Multi-user mode toggle and delivery settings

### User Management System (NEW)

CLI-based user management:
- Users are managed by administrators via CLI commands
- Subscriptions support categories (cs.AI, cs.LG) and keywords (transformer, LLM)
- Delivery history prevents duplicate paper delivery
- Backward compatible: single-user mode uses existing MAIL_TO_ADDRESS
```

在 "Development Notes" 部分更新：
- 移除 "The application is stateless" 描述
- 添加 SQLite 数据库相关说明

### 2. README.md 需要添加的内容

在 "功能概览" 部分添加：
```markdown
- **文献管理**：持久化存储论文，跨运行去重，避免重复处理
- **多用户订阅**：支持多用户按分类/关键词订阅，个性化邮件投递
```

添加新章节 "数据库配置"：
```markdown
## 数据库配置（v2.0+）

### 初始化数据库
\`\`\`bash
ai-mail-relay db init
\`\`\`

### 配置选项
| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `DATABASE_PATH` | SQLite 数据库路径 | `./data/ai_mail_relay.db` |
| `DATABASE_ENABLED` | 启用数据库存储 | `true` |
| `MULTI_USER_MODE` | 启用多用户模式 | `false` |
| `SKIP_DELIVERED_PAPERS` | 跳过已投递论文 | `true` |
```

添加新章节 "用户管理"：
```markdown
## 用户管理（多用户模式）

### 添加用户
\`\`\`bash
ai-mail-relay user add --email "user@example.com" --name "张三"
\`\`\`

### 管理订阅
\`\`\`bash
# 添加分类订阅
ai-mail-relay user subscribe --email "user@example.com" --categories "cs.AI,cs.LG"

# 添加关键词订阅
ai-mail-relay user subscribe --email "user@example.com" --keywords "transformer,LLM"

# 查看订阅
ai-mail-relay user subscriptions --email "user@example.com"

# 取消订阅
ai-mail-relay user unsubscribe --email "user@example.com" --categories "cs.CV"
\`\`\`

### 用户列表
\`\`\`bash
ai-mail-relay user list
ai-mail-relay user show --email "user@example.com"
\`\`\`
```

---

## 阶段一：文献存储与去重

### 1.1 新增模块结构

```
src/ai_mail_relay/
├── database/
│   ├── __init__.py
│   ├── connection.py      # SQLite 连接管理
│   └── migrations.py      # 数据库迁移
├── repositories/
│   ├── __init__.py
│   └── paper_repository.py  # 论文 CRUD
└── services/
    ├── __init__.py
    └── paper_service.py     # 去重逻辑
```

### 1.2 数据库表结构

```sql
CREATE TABLE papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    arxiv_id TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    authors TEXT NOT NULL,
    categories TEXT NOT NULL,        -- JSON: ["cs.AI", "cs.LG"]
    abstract TEXT,
    links TEXT,                      -- JSON: ["https://..."]
    affiliations TEXT,
    summary TEXT,                    -- LLM 摘要
    research_field TEXT,             -- 研究领域
    published_date DATE,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

CREATE INDEX idx_papers_arxiv_id ON papers(arxiv_id);
CREATE INDEX idx_papers_published_date ON papers(published_date);
```

### 1.3 配置扩展

新增环境变量：
```bash
DATABASE_PATH=./data/ai_mail_relay.db   # 数据库路径
DATABASE_ENABLED=true                    # 启用数据库（默认 true）
```

修改文件：[config.py](src/ai_mail_relay/config.py)
- 新增 `DatabaseConfig` 数据类

### 1.4 核心实现

**database/connection.py**
- `get_connection()`: 获取 SQLite 连接（单例模式）
- `init_database()`: 初始化表结构
- 使用 WAL 模式提升并发性能

**repositories/paper_repository.py**
- `insert(paper: ArxivPaper) -> int`
- `find_by_arxiv_id(arxiv_id: str) -> ArxivPaper | None`
- `find_unprocessed() -> List[ArxivPaper]`
- `update_summary(arxiv_id: str, summary: str, research_field: str)`
- `exists(arxiv_id: str) -> bool`

**services/paper_service.py**
- `deduplicate_and_store(papers: List[ArxivPaper]) -> List[ArxivPaper]`
  - 检查数据库中是否已存在（按 arxiv_id）
  - 新论文插入数据库
  - 返回需要处理的论文列表（新论文 + 未完成处理的论文）

### 1.5 Pipeline 集成

修改文件：[pipeline.py](src/ai_mail_relay/pipeline.py)

```python
# 原流程
papers = fetch_from_api(...)
filtered = filter_papers(papers, ...)
unique = deduplicate_papers(filtered)  # 内存去重
# ... LLM 处理 ...

# 新流程
papers = fetch_from_api(...)
filtered = filter_papers(papers, ...)
unique = deduplicate_papers(filtered)  # 内存去重（保留）

if settings.database.enabled:
    paper_service = PaperService(settings.database)
    to_process = paper_service.deduplicate_and_store(unique)  # 数据库去重
else:
    to_process = unique

# ... LLM 处理 ...

if settings.database.enabled:
    paper_service.save_summaries(processed_papers)  # 保存摘要
```

### 1.6 CLI 命令

修改文件：[main.py](src/ai_mail_relay/main.py)

新增子命令：
```bash
ai-mail-relay db init      # 初始化数据库
ai-mail-relay db status    # 查看数据库状态（论文数量等）
ai-mail-relay db backup    # 备份数据库
```

### 1.7 ArxivPaper 扩展

修改文件：[arxiv_parser.py](src/ai_mail_relay/arxiv_parser.py)

```python
@dataclass
class ArxivPaper:
    # 现有字段保持不变
    title: str
    authors: str
    categories: List[str]
    abstract: str
    links: List[str] = field(default_factory=list)
    affiliations: str = ""
    arxiv_id: str = ""
    summary: str = ""
    research_field: str = ""

    # 新增字段
    db_id: int | None = None
    published_date: date | None = None
```

---

## 阶段二：用户管理系统

### 2.1 新增表结构

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    sub_type TEXT NOT NULL,          -- 'category' 或 'keyword'
    value TEXT NOT NULL,             -- 如 'cs.AI' 或 'transformer'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, sub_type, value)
);

CREATE TABLE delivery_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    paper_id INTEGER NOT NULL,
    delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE,
    UNIQUE(user_id, paper_id)
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(is_active);
CREATE INDEX idx_subs_user ON user_subscriptions(user_id);
CREATE INDEX idx_delivery_user_paper ON delivery_history(user_id, paper_id);
```

### 2.2 新增模块

```
src/ai_mail_relay/
├── repositories/
│   ├── user_repository.py        # 用户 CRUD
│   └── subscription_repository.py # 订阅管理
├── services/
│   ├── user_service.py           # 用户业务逻辑
│   └── delivery_service.py       # 投递管理
└── cli/
    └── user_commands.py          # 用户管理命令
```

### 2.3 配置扩展

新增环境变量：
```bash
MULTI_USER_MODE=false              # 启用多用户模式（默认 false）
SKIP_DELIVERED_PAPERS=true         # 跳过已投递论文
```

### 2.4 核心实现

**repositories/user_repository.py**
- `create(email: str, name: str) -> int`
- `find_by_email(email: str) -> User | None`
- `find_active() -> List[User]`
- `deactivate(email: str)`
- `activate(email: str)`

**repositories/subscription_repository.py**
- `add_category(user_id: int, category: str)`
- `add_keyword(user_id: int, keyword: str)`
- `remove(user_id: int, sub_type: str, value: str)`
- `get_user_subscriptions(user_id: int) -> dict`

**services/user_service.py**
- `get_papers_for_user(user_id: int, papers: List[ArxivPaper]) -> List[ArxivPaper]`
  - 按用户订阅的分类和关键词过滤论文

**services/delivery_service.py**
- `filter_undelivered(user_id: int, papers: List[ArxivPaper]) -> List[ArxivPaper]`
- `record_delivery(user_id: int, paper_ids: List[int])`

### 2.5 CLI 用户管理命令

```bash
# 用户管理
ai-mail-relay user add --email "user@example.com" --name "张三"
ai-mail-relay user list
ai-mail-relay user show --email "user@example.com"
ai-mail-relay user deactivate --email "user@example.com"
ai-mail-relay user activate --email "user@example.com"

# 订阅管理
ai-mail-relay user subscribe --email "user@example.com" --categories "cs.AI,cs.LG"
ai-mail-relay user subscribe --email "user@example.com" --keywords "transformer,LLM"
ai-mail-relay user unsubscribe --email "user@example.com" --categories "cs.CV"
ai-mail-relay user subscriptions --email "user@example.com"
```

### 2.6 邮件发送适配

修改文件：[mail_sender.py](src/ai_mail_relay/mail_sender.py)

**单用户模式（默认，向后兼容）**：
- 使用 `MAIL_TO_ADDRESS` 作为收件人
- 使用全局 `ARXIV_ALLOWED_CATEGORIES` 和 `ARXIV_KEYWORDS` 过滤

**多用户模式**：
- 遍历所有活跃用户
- 按用户订阅过滤论文
- 排除已投递论文
- 发送个性化邮件
- 记录投递历史

### 2.7 Pipeline 适配

修改文件：[pipeline.py](src/ai_mail_relay/pipeline.py)

```python
if settings.multi_user.enabled:
    # 多用户模式
    users = user_service.get_active_users()
    for user in users:
        user_papers = user_service.get_papers_for_user(user.id, processed_papers)
        undelivered = delivery_service.filter_undelivered(user.id, user_papers)
        if undelivered:
            sender.send_digest_to_user(user, undelivered, report_date)
            delivery_service.record_delivery(user.id, [p.db_id for p in undelivered])
else:
    # 单用户模式（向后兼容）
    sender.send_digest(summary, processed_papers, report_date)
```

---

## 关键文件修改清单

### 阶段一
| 文件 | 操作 | 说明 |
|------|------|------|
| `src/ai_mail_relay/config.py` | 修改 | 添加 DatabaseConfig |
| `src/ai_mail_relay/arxiv_parser.py` | 修改 | 添加 db_id, published_date 字段 |
| `src/ai_mail_relay/pipeline.py` | 修改 | 集成数据库去重 |
| `src/ai_mail_relay/main.py` | 修改 | 添加 db 子命令 |
| `src/ai_mail_relay/database/__init__.py` | 新增 | |
| `src/ai_mail_relay/database/connection.py` | 新增 | SQLite 连接管理 |
| `src/ai_mail_relay/database/migrations.py` | 新增 | 表结构迁移 |
| `src/ai_mail_relay/repositories/__init__.py` | 新增 | |
| `src/ai_mail_relay/repositories/paper_repository.py` | 新增 | 论文 CRUD |
| `src/ai_mail_relay/services/__init__.py` | 新增 | |
| `src/ai_mail_relay/services/paper_service.py` | 新增 | 去重逻辑 |

### 阶段二
| 文件 | 操作 | 说明 |
|------|------|------|
| `src/ai_mail_relay/config.py` | 修改 | 添加 MultiUserConfig |
| `src/ai_mail_relay/pipeline.py` | 修改 | 多用户投递流程 |
| `src/ai_mail_relay/mail_sender.py` | 修改 | 支持多用户发送 |
| `src/ai_mail_relay/main.py` | 修改 | 添加 user 子命令 |
| `src/ai_mail_relay/database/migrations.py` | 修改 | 添加用户表 |
| `src/ai_mail_relay/repositories/user_repository.py` | 新增 | 用户 CRUD |
| `src/ai_mail_relay/repositories/subscription_repository.py` | 新增 | 订阅管理 |
| `src/ai_mail_relay/services/user_service.py` | 新增 | 用户业务逻辑 |
| `src/ai_mail_relay/services/delivery_service.py` | 新增 | 投递管理 |
| `src/ai_mail_relay/cli/user_commands.py` | 新增 | 用户 CLI |

---

## 向后兼容保证

1. **默认行为不变**：
   - `DATABASE_ENABLED=true`（默认启用数据库）
   - `MULTI_USER_MODE=false`（默认单用户模式）

2. **单用户模式**：
   - 继续使用 `MAIL_TO_ADDRESS` 作为收件人
   - 继续使用全局 `ARXIV_ALLOWED_CATEGORIES` 和 `ARXIV_KEYWORDS`

3. **渐进迁移**：
   - 现有部署只需运行 `ai-mail-relay db init` 初始化数据库
   - 无需修改现有环境变量即可获得去重功能

---

## 实现顺序

### 阶段一（文献存储与去重）
1. 创建 database 模块（connection.py, migrations.py）
2. 创建 paper_repository.py
3. 创建 paper_service.py
4. 修改 config.py 添加 DatabaseConfig
5. 修改 arxiv_parser.py 添加新字段
6. 修改 pipeline.py 集成数据库
7. 修改 main.py 添加 db 命令
8. 测试验证

### 阶段二（用户管理）
1. 扩展 migrations.py 添加用户表
2. 创建 user_repository.py
3. 创建 subscription_repository.py
4. 创建 user_service.py
5. 创建 delivery_service.py
6. 创建 cli/user_commands.py
7. 修改 config.py 添加 MultiUserConfig
8. 修改 mail_sender.py 支持多用户
9. 修改 pipeline.py 多用户流程
10. 修改 main.py 添加 user 命令
11. 测试验证
