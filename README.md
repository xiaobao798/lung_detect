# 全国医保影像 AI 识图大赛赛道一

本仓库用于赛道一“基于 CT 的肺癌智能检测”自建模型组开发。当前版本首先解决推理服务、结果格式、目录结构和 callback 闭环；模型能力将在官方可信环境中逐步接入。

## 当前状态

- 已实现 `GET /health`；
- 已实现异步 `POST /call`；
- 已实现基于 `evaluation_id` 的结果目录；
- 已实现 `prediction.json` 和 `duplicate_pairs.jsonl` 校验；
- 已实现结果原子写入、任务幂等和 callback 重试；
- 已提供完全合成的单元测试；
- 当前预测器是格式基线，不具备进入比赛排名所需的模型精度。

## 合规边界

不要向本仓库提交官方数据、真实 UID、医学影像、受限模型权重、预测结果、训练日志、平台凭证或 callback 地址。比赛数据只能在官方可信环境中使用。GitHub 不能替代赛事要求的统一开发管理平台。

## 目录

```text
src/lung_ai/        推理服务和结果生成代码
tests/              只使用合成数据的测试
configs/            非敏感配置模板
scripts/            本地和容器启动脚本
docs/               规范核对和实施文档
```

## 本地运行

需要 Python 3.10 或更高版本。第一阶段只使用 Python 标准库。

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
python -m lung_ai.server
```

服务默认监听 `0.0.0.0:8000`。本地运行时可使用环境变量覆盖目录：

```powershell
$env:LUNG_AI_ANSWER_BASE = "$PWD\local-answer"
$env:LUNG_AI_CALLBACK_URL = "http://127.0.0.1:9000/callback"
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

推理请求：

```bash
curl -X POST http://127.0.0.1:8000/call \
  -H "Content-Type: application/json" \
  -d '{
    "request_id":"local-request-1",
    "team_id":"local-team",
    "track_code":"track-one",
    "input":{
      "evaluation_id":"local-evaluation-1",
      "dataset_path":"/absolute/path/to/synthetic-dataset"
    }
  }'
```

## 官方环境配置

比赛环境至少需要设置：

```text
LUNG_AI_ANSWER_BASE=/2026aicompetition/workspace/answer
LUNG_AI_CALLBACK_URL=<容器实例页面显示的完整 callback 地址>
LUNG_AI_CALLBACK_PRED_PATH_MODE=evaluation
```

`LUNG_AI_CALLBACK_PRED_PATH_MODE` 支持 `evaluation` 和 `predicate`。官方文档对此存在歧义，第一次验证测评时需要确认。

启动命令必须保持前台运行：

```bash
bash /2026aicompetition/workspace/common/lung-ai/scripts/start.sh
```

## 当前数据假设

第一版扫描器假设 `dataset_path` 下的真实检查采用以下结构：

```text
<patientid>/<studyid>/<seriesuid>/<image>.nii.gz
```

文件名以 `AI-肺结节检测;` 或 `heatmap_` 开头时会被忽略。进入可信环境后，必须用实际测试样例验证这一假设。

## 开发里程碑

1. 合成数据端到端测试；
2. 官方验证测评形成有效结果；
3. 假人体、拼接和重复影像最低模型；
4. 接入官方肺结节检测或分割模型；
5. 病灶属性分类；
6. 冻结镜像并正式提交。

详细规范核对见 [docs/official-spec-audit.md](docs/official-spec-audit.md)。

无法在可信环境使用 Codex 时，请按照
[docs/trusted-environment-runbook.md](docs/trusted-environment-runbook.md)
运行只读检查脚本。脚本不会读取影像或标签内容，也不会记录患者、检查和序列目录名。
