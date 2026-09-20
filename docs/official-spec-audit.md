# 赛道一官方资料核对记录

本记录依据赛事开发规范 V2.0、公共数据集格式说明、初赛评审规则简要说明和参赛指引手册整理。它用于指导代码实现，但不能替代验证测评；官方材料中的示例存在非严格 JSON、字段位置不一致和必填规则冲突，必须通过平台验证确定最终解析行为。

## 1. 已确认的比赛闭环

- 初赛在无公网的可信云桌面和训推容器内完成，比赛数据禁止下载。
- 所有参赛队伍需要接入官方统一开发管理平台。GitHub 可作为个人私有开发仓库，但不能取代官方平台，也不得包含比赛数据、受限权重、真实 UID、凭证或敏感日志。
- 普通容器用于开发、训练和调试；正式验证和测评必须使用测评容器。
- 服务必须监听 `0.0.0.0:8000`，实现 `GET /health` 和 `POST /call`。
- `/call` 必须在 5 秒内返回 HTTP 200，实际推理在后台异步执行。
- 必须从请求中的 `input.dataset_path` 动态读取批量测试数据，并保存原始 `request_id` 和 `evaluation_id`。
- 推理完成后，结果放入 `/2026aicompetition/workspace/answer/{evaluation_id}/`，再调用平台页面提供的 callback 地址。
- callback 请求包含原 `request_id`、`evaluationId` 和 `predPath`。
- 测评容器启动命令必须是长期运行的前台进程；启动探针最长等待 30 分钟，成功后等待 60 秒就绪；探活每 30 秒一次，连续失败 3 次会重启容器。
- 每个赛道每天有 10 次验证测试机会。
- 进入正式测评后容器被冻结，不能继续修改模型或训练参数。

## 2. 训练日志硬性要求

训练日志必须采用 JSONL，路径为：

```text
/2026aicompetition/workspace/logs
```

每行必须是一个独立 JSON 对象。必填字段：

- `timestamp`
- `epoch`
- `step`
- `phase`，值为 `train`、`val` 或 `test`
- `mode`，值为 `training` 或 `inference`
- `data_source`

可选字段包括 `loss`、`lr`、`checkpoint`、`pretrained_from`。日志必须来自真实运行，不应伪造。

## 3. 数据与输出目录

赛道一真实影像为 NIfTI。训练标注结构为：

```text
annotation/<patientid>/<studyid>/<seriesuid>/<原始影像>.nii.gz
annotation/<patientid>/<studyid>/<seriesuid>/<lesionid>/AI-肺结节检测;.nii.gz
annotation/<patientid>/<studyid>/<seriesuid>/<lesionid>/AI-肺结节检测;.txt
```

特殊影像位于训练标注目录下的：

- `Composition`：拼接影像阳性；
- `fake`：假人体阳性；
- `duplicate`：重复影像样本和金标准。

预测结果结构为：

```text
predicate/
├── duplicate_pairs.jsonl
└── <patientid>/
    └── <studyid>/
        ├── prediction.json
        └── <seriesuid>/
            └── heatmap_<LesionID>.nii.gz
```

代码中应将结果集根目录建模为：

```text
/2026aicompetition/workspace/answer/{evaluation_id}/predicate
```

callback 的 `predPath` 是否传 `.../{evaluation_id}` 还是 `.../{evaluation_id}/predicate`，官方文字与示例不够一致，必须在第一次验证测评中确认。

## 4. 医保安全任务决定能否进入排名

赛道一必须完成以下三项：

- 非人体影像识别：Partial AUC-PR，Recall 区间为 5% 至 50%；
- 拼接影像识别：Partial AUC-PR，Recall 区间为 5% 至 50%；
- 重复影像识别：AUC-PR。

三项构成医保安全得分的调和平均值。任何一项为 0 时，医保安全得分直接为 0。组委会还会为 Top-K、Recall@10%FPR、Precision@15%Recall 等指标设置门槛，具体门槛拟在正式推理测试前 48 小时公布。任一门槛未达到，不参加初赛总分排名，也不能晋级决赛。

因此，常量预测只适合作为格式闭环。最低可排名版本必须至少实现：

1. 假人体二分类；
2. 拼接影像二分类；
3. 重复影像检索与成对概率输出。

测试集中每一例影像，无论模型判断是真实还是伪造，都必须输出全部医保安全和临床诊断结果。评分端依据金标准选择真实病例计算临床任务，不能因为模型判定为伪造就省略临床字段。

## 5. 赛道一临床得分结构

临床诊断得分内部权重为：

- 结节检测和良恶性分类：40%；
- 主恶性病灶病理分型和 T 分期：20%；
- 密度、位置、大小和伴随征象：40%。

结节匹配规则：预测中心点与真实中心点的物理空间欧氏距离不超过：

```text
min(max(真实结节平均直径 × 0.6, 2.0 mm), 15.0 mm)
```

一个金标准结节匹配到多个预测点时，只保留置信度最高者作为真阳性，其余忽略。

结节检测以 FROC 平均敏感度评分，同时单独考核直径小于 10 mm 的微小结节。良恶性采用 ROC-AUC；漏检恶性结节以 `MalignancyScore=0` 参与排序。

漏检结节的密度、大小、位置和伴随征象全部记 0。检测成功且为金标准恶性的主病灶才参与病理分型和 T 分期。由此可见，结节检测是临床任务的前置瓶颈，应优先于复杂属性分类。

## 6. 赛道一强制编码

### 病理分型

```text
Adenocarcinoma
Squamous
SmallCell
LargeCell
Other
```

### T 分期

`T_Staging.value` 使用字符串 `"1"` 至 `"4"`，`confidence` 必须包含四个键且概率和为 1。

### 密度

```text
Solid
PartSolid
GroundGlass
Calcified
```

### 大小

```text
MicroNodule
SmallNodule
Nodule
Mass
```

### 伴随征象

```text
Lobulation
Spiculation
SpineSign
PleuralTag
VesselConvergence
BronchialCutoff
VacuoleSign
Cavity
LiquefactionNecrosis
AirBronchogram
HaloSign
None
```

伴随征象是 12 个独立二分类概率，概率和不要求等于 1。

### 位置

位置是 19 类单标签多分类，必须完整输出所有类别，概率和为 1：

```text
RightUpperLobe/Apical
RightUpperLobe/Posterior
RightUpperLobe/Anterior
RightMiddleLobe/Lateral
RightMiddleLobe/Medial
RightLowerLobe/Superior
RightLowerLobe/MedialBasal
RightLowerLobe/AnteriorBasal
RightLowerLobe/LateralBasal
RightLowerLobe/PosteriorBasal
LeftUpperLobe/Apicoposterior
LeftUpperLobe/Anterior
LeftUpperLobe/SuperiorLingular
LeftUpperLobe/InferiorLingular
LeftLowerLobe/Superior
LeftLowerLobe/AnteromedialBasal
LeftLowerLobe/LateralBasal
LeftLowerLobe/PosteriorBasal
Pleura
```

## 7. 重复影像输出

文件名固定为 `duplicate_pairs.jsonl`。每行字段：

```json
{"StudyUID":"J","StudyUID_dup":"K","PairProb":0.96}
```

要求：

- 每行是独立、严格合法的 JSON，不带尾逗号；
- `PairProb` 位于 `[0,1]`；
- 两个 UID 均来自本次测试集；
- 正反顺序视为同一对，评分端取重复记录中的最高概率；
- 每例检查最多提交 Top-200 候选对；
- 未输出的 pair 默认概率为 0；
- 文件至少包含一条有效记录。

## 8. 官方资料中的实现风险与冲突

以下问题不能照抄示例，必须建立严格 schema 并用验证测评确认：

1. 开发规范中的 `prediction.json` 示例包含注释、省略号和部分尾逗号，不是可直接解析的 JSON。
2. `duplicate_pairs.jsonl` 示例每行末尾带逗号，实际实现不得保留。
3. 阳性示例未展示必填的 `ProcessingTime_ms`。
4. 示例把 `Interpretation` 放在 `Prediction` 内；早期上下文和字段描述的层级表达不完全一致。
5. `AttentionMap` 在字段表中标为必填，但评审规则称热力图只用于决赛、初赛不计分。初赛是否允许空数组或省略需要验证。
6. `BoundingBox` 被标为推荐输出，但中心点是结节匹配的核心；代码必须始终输出合法 `KeyPoints`。
7. FROC 需要预测中心点置信度。现有格式最可能使用 `KeyPoints[].confidence`，但官方材料未明确说明，应确认。
8. 良性病灶可省略 T 分期，但字段表又把 `T_Staging.confidence` 标为必填，存在冲突。
9. `predPath` 的末级目录不明确。
10. `BoundingBox` 的坐标系和六个数字的确切含义未明确；关键点明确要求物理空间毫米坐标。
11. 输出结构图中的热力图目录排版存在换行歧义，需要用验证测评确认文件位置。

## 9. 修订后的最低成本路线

### 阶段 1 格式与服务闭环

使用合成 NIfTI 数据完成 API、目录、JSON、JSONL、callback 和幂等任务测试。常量预测仅用于此阶段。

### 阶段 2 医保安全最低模型

- 假人体：以低分辨率 3D/2.5D 分类器或官方公共模型训练二分类；
- 拼接影像：以低分辨率多切片分类器训练二分类；
- 重复影像：重采样后生成全局 embedding，使用近邻检索输出每例 Top-K，再用相似度校准 `PairProb`。

这三项需要优先做到非零且可排序，因为它们决定是否具有排名资格。

### 阶段 3 结节检测

优先接入官方公共肺结节检测或分割模型。若只有分割输出，则通过连通域生成病灶中心点、直径和框。没有官方模型时，优先复用赛事提供的 baseline，不自研复杂网络。

### 阶段 4 低成本属性预测

对已检出的病灶裁剪 patch，以共享 3D 编码器加多个轻量分类头预测：

- 良恶性；
- 密度；
- 大小；
- 位置；
- 伴随征象；
- 仅恶性主病灶使用的病理和 T 分期。

大小类别和平均直径可优先由分割/检测几何量直接计算。位置可由肺叶分割或公共模型推导。复杂病理和 T 分期最后实现。

### 阶段 5 冻结提交

验证测评通过后固定代码提交号、镜像摘要、权重哈希和配置。正式测评前只修复阻断问题，不再升级框架或大改模型。
