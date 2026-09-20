# 可信环境检查操作说明

这份操作说明用于在无法运行 Codex 的赛事可信环境中收集非敏感工程信息。检查脚本只读取目录元数据，不打开影像、标注或标签文件，也不记录患者、检查或序列目录名。

## 1. 将代码带入可信环境

优先通过赛事要求的统一开发管理平台同步代码。如果尚未配置官方代码仓库，也可以使用赛事明确允许的文件上传方式，将本仓库源码压缩包带入云桌面。不要把比赛数据或可信环境生成的结果反向上传到 GitHub。

## 2. 运行检查

在普通训练容器中进入项目目录，然后执行：

```bash
python scripts/inspect_trusted_environment.py
```

默认报告写入：

```text
/2026aicompetition/workspace/common/lung-ai/trusted_environment_report.json
```

如果项目或持久化目录不同，可以指定输出路径：

```bash
python scripts/inspect_trusted_environment.py \
  --output /2026aicompetition/workspace/common/trusted_environment_report.json
```

## 3. 查看报告

```bash
python -m json.tool \
  /2026aicompetition/workspace/common/lung-ai/trusted_environment_report.json \
  | less
```

重点查看 `system`、`packages`、`torch`、`nvidia_smi`、`public_models` 和 `training_data`。

## 4. 信息安全

报告没有读取文件内容，也没有记录训练数据目录名，但仍应默认留在可信环境。只有赛事规则允许时，才复制或转述以下工程信息：

- Python、PyTorch、CUDA 和 cuDNN 版本；
- GPU 型号和显存；
- 已安装依赖版本；
- 官方 `public_models` 中与肺、结节、CT 相关的公共模型名称；
- 数据集文件类型和数量的汇总统计；
- 不包含任何 ID 的目录层级统计。

不要复制真实路径中的患者 ID、StudyUID、SeriesUID、标签内容、影像元数据或任何影像文件。

## 5. 下一轮需要的信息

获得允许分享的结果后，优先提供：

1. `system`、`packages`、`torch` 和 `nvidia_smi`；
2. `public_models.files` 中与 `lung`、`nodule`、`ct`、`segmentation`、`detection`、`nnunet` 相关的条目；
3. `training_data` 的汇总统计；
4. 脚本运行时的报错文本，如有。

据此可以决定依赖版本、公共模型接入方式和下一步训练路线。
