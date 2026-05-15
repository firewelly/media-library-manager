# Release 使用说明

本目录包含运行 `production_video_analyzer_fixed.py` 所需的全部代码与资源，支持在本地进行视频标签分析并将结果写入数据库与 CSV。

## 目录结构

- `production_video_analyzer_fixed.py`：生产分析主脚本，负责从数据库读取未标记视频，调用分析器执行分析，写入数据库与生成 CSV 报告。
- `video_analyzer_local_model_adult.py`：基于 SiliconFlow Qwen3-VL-30B-A3B 的视频帧分析器（MoE架构），包含标签判定逻辑与提示词生成。
- `video_analyzer_pipeline.py`：流水线分析器，帧提取串行+API调用并行，最大化资源利用率。
- `adapter.py`：GUI桥接层，为 media_library.py 提供统一的视频分析接口。
- `video_integrity.py`：视频完整性检查工具，提供基础可播放与 seeking 跳转检测，避免损坏文件导致卡死。
- `vocabulary_tags.txt`：标签词汇表（122个标签），分析器会从此文件加载可判定的标签集合。
- `requirements_video_analyzer.txt`：运行所需的 Python 包。

## 环境要求

- Python 3（建议 3.9+）
- 可以访问 SiliconFlow API 的网络环境
- 已安装 `requirements_video_analyzer.txt` 中列出的依赖

## 安装依赖

```bash
pip install -r requirements_video_analyzer.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

如不使用清华源，可去掉 `-i` 参数。

## 配置说明

- **模型**：`Qwen/Qwen3-VL-30B-A3B-Instruct`（MoE架构，只激活3B参数，比8B更快更强）
- **API地址**：`https://api.siliconflow.cn`
- **视频处理**：
  - 动态帧提取：超过10分钟的视频按每分钟1帧，最多30帧，均匀覆盖全程
  - 10分钟以内视频固定8帧
  - 图片压缩：宽度640px，最大0.4MB
  - 标签数量：最多7个（特殊特征优先）
- **分析规则**：
  - **只关注女性主角特征，完全忽略男性人物**
  - 流水线模式：边完成边写入数据库（中断不丢失，已写入的标签保留）
  - 自动过滤离线文件夹和实际不存在的文件

## 模型对比（测试验证）

| 对比项 | Qwen3-VL-8B | Qwen3-VL-30B-A3B |
|--------|-------------|-------------------|
| 架构 | 传统Dense | **MoE（激活3B）** |
| 平均响应速度 | 慢 | **快2-3倍** |
| 识别成功率 | 较低（部分视频输出全部"无"） | **100%识别率** |
| 剧情细节 | 较笼统 | **更丰富具体** |
| 价格 | 相近 | **相近** |

> 30B模型识别能力显著优于8B，且价格相近，推荐使用。

## 标签优先级

```
特殊特征（最高） → 哺乳、乳汁、孕妇、萝莉、人妖
服装特征         → 黑丝、制服、情趣装、丝袜、眼镜
情节特征         → 偷情、出轨、调教、绿帽
人物特征         → 少妇、人妻、熟女、巨乳
行为特征（最低） → 自慰、口交、后入、内射
```

## API 密钥

- 优先从环境变量 `SILICONFLOW_API_KEY` 读取。
- 也可在运行时通过 `--api-key` 参数传入。

示例设置环境变量：

```bash
export SILICONFLOW_API_KEY="你的SiliconFlow密钥"
```

## 快速开始

1. 安装依赖
   ```bash
   pip install -r requirements_video_analyzer.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
   ```

2. 运行主脚本（需提供数据库路径）
   ```bash
   cd /Users/firewell/bin/media/video_analyzer && python3 production_video_analyzer_fixed.py --verbose
   ```

3. **推荐：流水线模式全量补标签（帧提取串行 + API并行，速度提升3-5倍）**
   ```bash
   cd /Users/firewell/bin/media/video_analyzer && python3 production_video_analyzer_fixed.py --pipeline --workers 10 --verbose
   ```

4. 测试模式（只处理10个视频）
   ```bash
   cd /Users/firewell/bin/media/video_analyzer && python3 production_video_analyzer_fixed.py --pipeline --workers 10 --limit 10 --verbose
   ```

5. 指定数据库路径
   ```bash
   cd /Users/firewell/bin/media/video_analyzer && python3 production_video_analyzer_fixed.py --db "/path/to/media_library.db" --pipeline --workers 10 --verbose
   ```

6. 跳过交互直接处理所有在线文件夹
   ```bash
   cd /Users/firewell/bin/media/video_analyzer && python3 production_video_analyzer_fixed.py --pipeline --workers 10 --all --verbose
   ```

## 参数说明

- `--db`：SQLite 数据库文件路径，默认为 `../media_library.db`
- `--output`：输出目录（日志与 CSV），默认当前脚本目录
- `--verbose`：显示详细信息
- `--limit`：限制处理的视频数量（测试用）
- `--api-key`：显式传入 SiliconFlow API 密钥
- `--all`：跳过交互模式，直接处理所有在线管理文件夹
- `--pipeline`：**启用流水线模式（帧提取串行+API并行），推荐开启**
- `--workers`：**API并行数**（默认3，**建议10**，API限速1000次/分钟，无需顾虑）

> `--workers` 限制的是同时等待API响应的线程数，不影响帧提取。帧提取始终是单线程串行，不抢占CPU资源。

## 工作流程

```
帧提取线程（串行，1个CPU线程）：
  视频1 → 视频2 → 视频3 → 视频4 → 视频5 → ...

API调用线程（并行，workers=N）：
  [API1] [API2] ... [APIn]  ← 同时N个在等待响应
  ↓完成一个，立即补充下一个（从已提取完成的队列中取）

效果：CPU提取帧不中断，API等待时间被充分利用
```

## 标签词汇表

- 编辑 `vocabulary_tags.txt` 可调整可判定标签集合（当前122个标签）。
- 分析器会在提示词中动态嵌入标签，并在返回结果末尾生成"匹配标签：标签1、标签2…"的行，主脚本会解析该行并写入数据库与 CSV。

## 输出与结果

- CSV 报告：`production_analysis_YYYYMMDD_HHMMSS.csv`
  - 字段：视频ID、标题、文件路径、标签数量、标签列表、描述、分析时间、错误信息等
- 日志：`analysis_log.txt`
- 数据库：将标签与描述写回 `videos` 表（字段：`tags`、`description`），并记录更新时间
- **流水线模式：边完成边写入数据库，中断后已完成的标签保留，不会丢失**

## 常见问题

- **运行报错"数据库文件不存在"**：检查 `--db` 指定路径是否有效
- **"未找到需要分析的视频"**：确保 `videos` 表中存在在线且无标签的视频记录；或切换到 `--all` 模式并确认 `folders` 表中的在线文件夹
- **API 调用失败**：检查 `SILICONFLOW_API_KEY` 是否正确、网络是否可达，必要时稍后重试
- **视频读取失败或卡死**：`video_integrity.py` 的完整性与跳转检测可过滤有问题的视频文件
- **中断后重新运行**：已打标签的视频会自动跳过，无需担心重复处理
- **database is locked**：并行写入数据库时可能出现，不影响已经写入的数据，重新运行即可
