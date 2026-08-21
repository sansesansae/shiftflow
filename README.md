# ShiftFlow 餐饮门店排班助手

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Next.js](https://img.shields.io/badge/Frontend-Next.js-blue)
![FastAPI](https://img.shields.io/badge/Backend-FastAPI-green)
![Supabase](https://img.shields.io/badge/Database-Supabase-3ecf8e)
![Langfuse](https://img.shields.io/badge/Observability-Langfuse-orange)

ShiftFlow 是一个面向奶茶、咖啡和快餐门店的 AI 排班工作台。它聚焦餐饮门店的日常排班、缺口补位、用工预测和经营复盘，支持门店/员工/班次数据看板、补位风险校验、小时级工时预测、CSV 经营数据导入、Supabase 数据持久化、Langfuse 对话质量追踪，以及 Vercel + Render 线上部署。

线上体验：

- 代码仓库：[https://github.com/sansesansae/shiftflow](https://github.com/sansesansae/shiftflow)
- 前端：[https://ui-three-red.vercel.app](https://ui-three-red.vercel.app)
- 后端健康检查：[https://shiftflow-backend-t7n9.onrender.com/health](https://shiftflow-backend-t7n9.onrender.com/health)
- 预测接口示例：[https://shiftflow-backend-t7n9.onrender.com/forecasts/summary](https://shiftflow-backend-t7n9.onrender.com/forecasts/summary)

![ShiftFlow Screenshot](screenshot.jpg)

## 核心能力

- **门店排班看板**：展示门店、员工、班次、缺口班次、可补位伙伴。
- **确认补位流程**：店长选择缺口班次和伙伴，生成确认卡后提交补位。
- **补位风险校验**：后端校验岗位匹配、闭店能力、工时上限、重复排班、时间冲突、门店权限。
- **登录与门店权限**：基于 Supabase Auth 和门店权限表，支持店长/运营账号的写操作校验。
- **小时级工时预测**：根据门店、日期、小时、岗位、订单量、销售额、天气、促销等数据生成预测工时。
- **偏差复盘**：计算预测工时与实际工时的偏差率，标记高偏差 badcase。
- **CSV 数据导入**：支持从页面上传经营数据 CSV，写入 `hourly_store_metrics` 后自动刷新预测和评估。
- **Langfuse 追踪**：后端对对话链路进行 trace，便于观察 badcase 和响应质量。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Next.js, React, TypeScript, Tailwind CSS, Material UI |
| 后端 | Python, FastAPI, OpenAI Agents SDK |
| 模型接入 | OpenAI-compatible client，可配置 DeepSeek / LiteLLM / OpenAI-compatible API |
| 数据库 | Supabase Postgres，SQLite seed fallback |
| 鉴权 | Supabase Auth + 后端写入口令 |
| 观测 | Langfuse + OpenInference instrumentation |
| 部署 | Vercel 前端，Render Python 后端 |

## 项目结构

```text
.
├── python-backend/
│   ├── main.py                         # FastAPI API 入口
│   ├── airline/
│   │   ├── agents.py                   # 对话助手与工具编排
│   │   ├── schedule_repository.py      # Supabase/SQLite 数据访问与排班逻辑
│   │   ├── tools.py                    # 排班工具函数
│   │   └── guardrails.py               # 输入/安全校验
│   ├── data/
│   │   ├── schema.sql                  # SQLite fallback schema
│   │   ├── generate_seed_data.py       # 餐饮门店演示数据生成
│   │   └── shiftflow_seed.sqlite       # 本地演示数据库
│   ├── ml/
│   │   └── labor_forecast.py           # 工时预测模型 smoke harness 内核
│   └── evals/
│       ├── model_baselines.json        # 模型评估阈值
│       ├── model_harness.md            # 模型 harness 说明
│       ├── shiftflow_cases.json        # 产品验收用例
│       └── shiftflow_harness.py        # 自动验收脚本
├── ui/
│   ├── app/page.tsx                    # ShiftFlow 前端工作台
│   ├── lib/api.ts                      # 前端 API 封装
│   └── lib/types.ts                    # 前端类型定义
├── supabase/
│   ├── migrations/                     # Supabase schema 迁移
│   ├── seed_shiftflow_demo.sql         # 演示数据 seed
│   └── auth-permissions.md             # Auth 与权限说明
└── render.yaml                         # Render 后端部署配置
```

## 数据模型

当前业务核心表包括：

- `stores`：门店信息。
- `employees`：员工、岗位、技能、工时上限。
- `shift_templates`：班次模板。
- `shifts`：具体日期班次与缺口。
- `shift_assignments`：员工排班记录。
- `shift_change_records`：调班/补位记录。
- `user_profiles`：用户角色。
- `user_store_permissions`：门店权限。
- `audit_logs`：写操作审计。
- `hourly_store_metrics`：小时级经营事实数据。
- `labor_forecasts`：预测工时结果。
- `forecast_evaluations`：预测与实际工时偏差评估。

## 预测逻辑

V2 当前采用可解释的 baseline 预测，而不是直接上复杂模型：

```text
预测工时 = 历史同门店 / 同岗位 / 同小时实际工时均值
        × 周末、节假日、促销、天气等修正系数
```

偏差率计算方式：

```text
偏差率 = (实际工时 - 预测工时) / 预测工时
```

含义：

- 正偏差：实际用工高于预测，说明预测低估。
- 负偏差：实际用工低于预测，说明预测高估。
- 高偏差时段会被标记为 `badcase`，用于后续模型训练和运营复盘。

后续可升级为 LightGBM/XGBoost，用真实 POS、考勤、天气、促销数据训练更稳定的工时预测模型。

## CSV 导入格式

页面支持导入小时经营数据 CSV。必填列：

```csv
metric_date,hour,role,order_count,sales_amount,actual_labor_hours
2026-08-19,12,调饮师,120,2880,4.0
```

可选列：

```csv
weather,temperature,is_weekend,is_holiday,promotion_flag
```

完整示例：

```csv
metric_date,hour,role,order_count,sales_amount,actual_labor_hours,weather,temperature,is_weekend,is_holiday,promotion_flag
2026-08-19,12,调饮师,120,2880,4.0,rain,30,false,false,true
2026-08-19,18,后厨,150,3600,5.0,clear,29,false,false,false
```

导入后，后端会：

1. 校验 CSV 字段和数据类型。
2. 写入 `hourly_store_metrics`。
3. 生成 `v2.1-import-baseline` 预测。
4. 写入 `labor_forecasts` 和 `forecast_evaluations`。
5. 刷新前端预测看板。

## 本地运行

### 1. 后端

```bash
cd python-backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3.11 -m uvicorn main:app --reload --port 8001
```

必要环境变量：

```bash
OPENAI_API_KEY=your_openai_compatible_key
OPENAI_BASE_URL=https://api.deepseek.com
AIRLINE_AGENT_MODEL=deepseek-v4-flash
AIRLINE_GUARDRAIL_MODEL=deepseek-v4-flash
OPENAI_TRACING_DISABLED=1
```

如果要连接 Supabase：

```bash
SUPABASE_URL=your_supabase_url
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key
SHIFT_WRITE_TOKEN=your_write_token
REQUIRE_SUPABASE_AUTH_FOR_WRITES=1
```

如果要启用 Langfuse：

```bash
LANGFUSE_PUBLIC_KEY=your_public_key
LANGFUSE_SECRET_KEY=your_secret_key
LANGFUSE_BASE_URL=https://us.cloud.langfuse.com
```

### 2. 前端

```bash
cd ui
npm install
npm run dev:next
```

前端默认连接：

```text
http://127.0.0.1:8001
```

可通过环境变量覆盖：

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001
NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
```

## 验收

后端语法检查：

```bash
cd python-backend
python3.11 -m py_compile main.py airline/schedule_repository.py ml/labor_forecast.py evals/shiftflow_harness.py
```

产品验收用例：

```bash
cd python-backend
python3.11 -m evals.shiftflow_harness
```

前端构建：

```bash
cd ui
npm run build
```

当前 harness 覆盖：

- 演示数据完整性。
- 未知门店不幻觉。
- 缺口班次真实存在。
- 员工技能结构化。
- 超工时补位阻断。
- 岗位不匹配阻断。
- 静默预测可计算偏差。
- CSV 导入后自动生成预测和评估。
- 预测模型 smoke harness：时间切分无泄漏、预测非负、MAE/MAPE/badcase rate 不超阈值、重复运行结果一致。

## 部署

### 后端 Render

后端部署配置在 `render.yaml`：

```yaml
rootDir: python-backend
buildCommand: pip install -r requirements.txt
startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT
healthCheckPath: /health
```

### 前端 Vercel

前端目录为 `ui/`。生产部署命令：

```bash
cd ui
npx vercel --prod --yes
```

当前生产地址：

```text
https://ui-three-red.vercel.app
```

## 当前版本状态

- `V1`：完成餐饮排班工作台、真实后端 API、Supabase 数据持久化。
- `V1.2`：完成补位确认卡、权限校验、排班风险校验。
- `V2`：完成小时级工时预测、偏差评估、badcase 看板。
- `V2.1`：完成 CSV 经营数据导入和预测刷新。

下一步建议：

- 增加独立预测复盘页。
- 增加 badcase 原因标注。
- 接真实 POS / 考勤数据。
- 引入 LightGBM 训练脚本。
- 将预测工时进一步转成排班建议。

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
