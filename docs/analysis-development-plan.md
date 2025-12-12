# 论文聚类与趋势分析功能开发方案

> **文档版本**: v1.1
> **更新日期**: 2025-12-11
> **目标**: 为 AI Mail Relay 添加论文聚类和研究趋势分析功能
> **本次进展概览**:
> - 新增 `AnalysisConfig`、Migration 3 以及 Embedding/Cluster 仓储
> - 实现基础 embedding 生成（Qwen API + 本地 fallback）、混合聚类、趋势快照与 Markdown 报告
> - CLI 增加 `ai-mail-relay analyze` 子命令（embed/cluster/trend/report）

---

## 1. 功能概述

### 1.1 核心需求

1. **聚类功能**: 混合方案 - 先用 `research_field` 粗分类，再用 embedding 细分
2. **趋势分析**: 用 LLM 分析各方向在当天/当周/当月的研究趋势变化
3. **输出形式**: Markdown/HTML 报告，为后续可视化前端预留接口
4. **触发方式**: 新的 CLI 命令 (`ai-mail-relay analyze`)

### 1.2 规模考虑

- 当前: ~100 篇论文
- 未来: 数万篇论文
- 需要: 分批处理、embedding 缓存、增量计算

---

## 2. 模块结构

```
src/ai_mail_relay/
├── analysis/                      # 新增: 分析模块
│   ├── __init__.py
│   ├── embeddings.py              # Embedding 生成与缓存
│   ├── clustering.py              # 混合聚类算法
│   ├── trends.py                  # LLM 趋势分析
│   └── report_generator.py        # 报告生成 (Markdown/HTML/JSON)
├── repositories/
│   ├── embedding_repository.py    # 新增: Embedding 存储
│   └── cluster_repository.py      # 新增: 聚类结果存储
├── services/
│   └── analysis_service.py        # 新增: 分析服务编排层
├── cli/
│   └── analyze_commands.py        # 新增: 分析 CLI 命令
└── api/                           # 新增: 前端 API 预留
    ├── __init__.py
    └── schemas.py                 # 数据传输对象定义
```

---

## 3. 数据库 Schema 变更

### 3.1 Migration 3: 分析相关表

```sql
-- 论文 Embedding 缓存
CREATE TABLE paper_embeddings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL UNIQUE,
    embedding BLOB NOT NULL,           -- numpy float32 序列化
    model_name TEXT NOT NULL,          -- 如 "text-embedding-v3"
    embedding_dim INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE
);

-- 聚类运行记录
CREATE TABLE cluster_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date DATE NOT NULL,
    date_range_start DATE NOT NULL,
    date_range_end DATE NOT NULL,
    algorithm TEXT NOT NULL,           -- "hierarchical_hybrid"
    num_clusters INTEGER NOT NULL,
    parameters TEXT,                   -- JSON 配置参数
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 聚类定义
CREATE TABLE clusters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    cluster_label TEXT NOT NULL,       -- LLM 生成的标签
    research_field_prefix TEXT,        -- 一级领域
    centroid BLOB,                     -- 聚类中心 embedding
    paper_count INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES cluster_runs(id) ON DELETE CASCADE
);

-- 论文-聚类关联
CREATE TABLE cluster_papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cluster_id INTEGER NOT NULL,
    paper_id INTEGER NOT NULL,
    distance_to_centroid REAL,
    FOREIGN KEY (cluster_id) REFERENCES clusters(id) ON DELETE CASCADE,
    FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE CASCADE,
    UNIQUE(cluster_id, paper_id)
);

-- 趋势分析快照
CREATE TABLE trend_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_date DATE NOT NULL,
    period_type TEXT NOT NULL,         -- 'daily', 'weekly', 'monthly'
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    field_trends TEXT NOT NULL,        -- JSON: field -> count
    analysis_summary TEXT,             -- LLM 生成的趋势分析
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(snapshot_date, period_type)
);

-- 索引
CREATE INDEX idx_embeddings_paper ON paper_embeddings(paper_id);
CREATE INDEX idx_cluster_runs_date ON cluster_runs(run_date);
CREATE INDEX idx_clusters_run ON clusters(run_id);
CREATE INDEX idx_clusters_field ON clusters(research_field_prefix);
CREATE INDEX idx_trends_date ON trend_snapshots(snapshot_date);
```

---

## 4. 配置扩展

在 `config.py` 中新增 `AnalysisConfig`:

| 环境变量 | 说明 | 默认值 |
|---------|------|--------|
| `EMBEDDING_PROVIDER` | Embedding 提供商 | `qwen` |
| `EMBEDDING_MODEL` | Embedding 模型 | `text-embedding-v3` |
| `EMBEDDING_DIM` | Embedding 维度 | `1024` |
| `EMBEDDING_BATCH_SIZE` | 批处理大小 | `25` (Qwen API 单次上限) |
| `CLUSTER_MIN_PAPERS` | 聚类最小论文数 | `3` |
| `CLUSTER_SIMILARITY_THRESHOLD` | 相似度阈值 | `0.75` |
| `CLUSTER_MAX_PER_FIELD` | 每个领域最大聚类数 | `20` |
| `TREND_LLM_MAX_PAPERS` | 趋势分析每次最大论文数 | `50` |
| `ANALYSIS_REPORT_DIR` | 报告输出目录 | `./reports` |
| `ANALYSIS_REPORT_FORMAT` | 报告格式 | `markdown` |

---

## 5. 聚类算法设计

### 5.1 两阶段混合聚类

```
Stage 1: 按 research_field 一级领域粗分组
         "计算机视觉 → 目标检测 → 小目标检测" → "计算机视觉"

Stage 2: 组内 Embedding 细聚类
         使用 Agglomerative Clustering + Cosine Distance
```

### 5.2 算法选择理由

- **Agglomerative Clustering**: 无需预设 k 值，支持 cosine distance，产生层级结构
- **Cosine Similarity**: 文本 embedding 标准度量
- **混合方案**: 利用已有的 `research_field` 语义信息，减少计算量

### 5.3 大规模数据处理策略

1. **Embedding 缓存**: 存入 SQLite，仅计算新论文
2. **分批生成**: 每批 25 篇，避免 API 超限
3. **增量聚类**: 按时间窗口聚类，复用历史 embedding
4. **内存优化**: 大数据量时使用 numpy memory-mapped arrays

---

## 6. CLI 命令设计

```bash
# 生成 Embedding（预计算）
ai-mail-relay analyze embed [--date-range START:END] [--force]

# 论文聚类
ai-mail-relay analyze cluster [--date-range START:END] [--output PATH] [--format markdown|html|json]

# 趋势分析
ai-mail-relay analyze trend --period daily|weekly|monthly [--compare] [--output PATH]

# 生成完整报告
ai-mail-relay analyze report [--date YYYY-MM-DD] [--output DIR]
```

---

## 7. 报告输出格式

### 7.1 Markdown 报告结构

```markdown
# arXiv AI 研究趋势报告
**生成日期**: 2025-01-15

## 统计概览
- 论文总数: 1250
- 分析时间范围: 2025-01-08 至 2025-01-15
- 聚类数量: 45

## 趋势分析

### 热门话题
- 大语言模型推理优化
- 多模态理解
- 视频生成

### 新兴趋势
- Agent 系统
- 检索增强生成 (RAG)

### 趋势总结
本周 AI 研究热点集中在...

## 论文聚类

### 计算机视觉
#### 图像生成 - Diffusion 方法 (23篇)
- **Paper Title 1** - 工作内容摘要
- **Paper Title 2** - 工作内容摘要
...
```

### 7.2 JSON Schema（前端预留）

```json
{
  "report_date": "2025-01-15",
  "statistics": {
    "total_papers": 1250,
    "clusters": 45,
    "date_range": ["2025-01-08", "2025-01-15"]
  },
  "trends": {
    "period_type": "weekly",
    "hot_topics": ["大语言模型推理优化", "多模态理解"],
    "emerging_trends": ["Agent系统"],
    "declining_topics": ["传统CNN架构"],
    "summary": "...",
    "field_distribution": {"计算机视觉 → 图像生成": 156},
    "time_series": [{"date": "2025-01-08", "field": "大语言模型", "count": 45}]
  },
  "clusters": [
    {
      "id": 1,
      "label": "LLM推理加速方法",
      "research_field_prefix": "自然语言处理",
      "paper_count": 23,
      "papers": [{"arxiv_id": "...", "title": "...", "summary": "..."}]
    }
  ]
}
```

---

## 8. 开发计划与进度追踪

### Phase 1: 基础设施

| 任务 | 状态 | 关键文件 |
|------|------|----------|
| 添加 `AnalysisConfig` 到 config.py | ✅ | `src/ai_mail_relay/config.py` |
| 创建 Migration 3 (分析表) | ✅ | `src/ai_mail_relay/database/migrations.py` |
| 实现 `EmbeddingRepository` | ✅ | `src/ai_mail_relay/repositories/embedding_repository.py` |
| 实现 `ClusterRepository` | ✅ | `src/ai_mail_relay/repositories/cluster_repository.py` |

### Phase 2: Embedding 服务

| 任务 | 状态 | 关键文件 |
|------|------|----------|
| 创建 `analysis/` 模块结构 | ✅ | `src/ai_mail_relay/analysis/__init__.py` |
| 实现 Embedding 生成 (Qwen) | ✅ | `src/ai_mail_relay/analysis/embeddings.py` |
| 实现 Embedding 缓存逻辑 | ✅ | `src/ai_mail_relay/analysis/embeddings.py` |
| 添加 `analyze embed` CLI 命令 | ✅ | `src/ai_mail_relay/cli/analyze_commands.py` |

### Phase 3: 聚类功能

| 任务 | 状态 | 关键文件 |
|------|------|----------|
| 实现 research_field 粗分组 | ✅ | `src/ai_mail_relay/analysis/clustering.py` |
| 实现 Embedding 细聚类 | ✅ | `src/ai_mail_relay/analysis/clustering.py` |
| 实现聚类结果持久化 | ✅ | `src/ai_mail_relay/services/analysis_service.py` |
| 添加 `analyze cluster` CLI 命令 | ✅ | `src/ai_mail_relay/cli/analyze_commands.py` |
| 基础 Markdown 报告生成 | ✅ | `src/ai_mail_relay/analysis/report_generator.py` |

### Phase 4: 趋势分析

| 任务 | 状态 | 关键文件 |
|------|------|----------|
| 实现领域分布统计 | ✅ | `src/ai_mail_relay/analysis/trends.py` |
| 设计 LLM 趋势分析 Prompt | ✅ | `src/ai_mail_relay/analysis/trends.py` |
| 实现趋势对比分析 | ✅ | `src/ai_mail_relay/analysis/trends.py` |
| 添加 `analyze trend` CLI 命令 | ✅ | `src/ai_mail_relay/cli/analyze_commands.py` |
| 趋势快照持久化 | ✅ | `src/ai_mail_relay/repositories/cluster_repository.py` |

### Phase 5: 报告与 API

| 任务 | 状态 | 关键文件 |
|------|------|----------|
| HTML 报告生成 | ✅ | `src/ai_mail_relay/analysis/report_generator.py` |
| JSON 输出 (前端预留) | ✅ | `src/ai_mail_relay/api/schemas.py` |
| 添加 `analyze report` CLI 命令 | ✅ | `src/ai_mail_relay/cli/analyze_commands.py` |
| 大数据量性能优化 | ⬜ | 多文件 |

> 报告格式默认由 `ANALYSIS_REPORT_FORMAT` 控制（支持 `markdown` / `html` / `json`），CLI 可通过 `--format` 覆盖，JSON payload 结构定义见 `api/schemas.py`。

---

## 9. 依赖项

需要添加到 `pyproject.toml`:

```toml
dependencies = [
    # 现有依赖...
    "numpy>=1.24.0",
    "scikit-learn>=1.3.0",    # 聚类算法
]
```

> 说明：新增依赖已写入 `pyproject.toml` 和 `requirements.txt`，重新安装 `pip install -e .` 即可。

---

## 10. Qwen Embedding API 技术细节

### 10.1 API 端点

```
POST https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding
```

### 10.2 请求格式

```python
{
    "model": "text-embedding-v3",
    "input": {
        "texts": ["文本1", "文本2", ...]
    },
    "parameters": {
        "dimension": 1024,        # 可选: 512, 1024, 1536
        "text_type": "document"   # document 或 query
    }
}

# Headers
{
    "Authorization": "Bearer {DASHSCOPE_API_KEY}",
    "Content-Type": "application/json"
}
```

### 10.3 响应格式

```python
{
    "output": {
        "embeddings": [
            {"text_index": 0, "embedding": [0.123, -0.456, ...]},
            {"text_index": 1, "embedding": [0.789, -0.012, ...]}
        ]
    },
    "usage": {
        "total_tokens": 150
    }
}
```

### 10.4 配置说明

| 环境变量 | 说明 |
|---------|------|
| `QWEN_API_KEY` 或 `LLM_API_KEY` | 阿里云 DashScope API Key |
| `EMBEDDING_MODEL` | 推荐 `text-embedding-v3` (最新) |
| `EMBEDDING_DIM` | 1024 (平衡效果和存储) |

### 10.5 限制

- 单次请求最多 25 个文本
- 每个文本最大 8192 tokens
- QPS 限制根据账户等级不同

---

## 11. 关键设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| Embedding 存储 | SQLite BLOB | 与现有架构一致，无需额外依赖 |
| 聚类算法 | Agglomerative | 无需预设 k，支持层级结构 |
| 距离度量 | Cosine | 文本 embedding 标准做法 |
| 报告格式 | Markdown 优先 | 简单、可读、易转换 |
| 前端数据 | JSON Schema | 标准化，便于前后端解耦 |

---

## 附录: 参考文件

实现时需要参考的现有代码:

- `src/ai_mail_relay/config.py` - 配置模式 (frozen dataclass)
- `src/ai_mail_relay/database/migrations.py` - Migration 装饰器模式
- `src/ai_mail_relay/repositories/paper_repository.py` - Repository 模式
- `src/ai_mail_relay/llm_client.py` - LLM 调用与并发处理
- `src/ai_mail_relay/cli/user_commands.py` - CLI 子命令模式
