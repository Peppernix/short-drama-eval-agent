# 短剧复刻自动评测 Agent（MVP）

这是一个用于面试实践的最小可运行项目：输入**原视频、用户修改指令、复刻视频**，先做镜头检测与自适应关键帧提取，可选加入 ASR 台词和 OCR 画面文字，再调用 OpenAI-compatible 多模态接口输出分维度评测结果和证据。

> 当前版本是“关键帧 + ASR + OCR”MVP：比只看静态帧多保留了台词和画面文字，但动作过程、运镜和音画同步仍需通过关键视频片段分析补足，不能把抽帧完全当作原视频的替代品。

## 所有文件都在哪里

整个项目只在当前 `short-drama-eval-agent/` 文件夹中工作；运行结果默认放在 `runs/`，虚拟环境放在 `.venv/`。删除整个文件夹即可完整清理。

## 目录

```text
short-drama-eval-agent/
├── src/drama_eval/       # 程序代码
├── tests/                # 测试
├── examples/             # 黄金样本格式示例
├── runs/                 # 本地运行结果（不会提交 Git）
├── .env.example          # API 配置示例
├── pyproject.toml
└── README.md
```

## 运行

```bash
cd "/Users/nauynix/Library/Application Support/AirJelly/sessions/e1125d04-928b-4929-94f0-fe32c8f4f6fa/short-drama-eval-agent"
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

只做镜头检测和抽帧，不调用模型：

```bash
drama-eval run \
  --original "/绝对路径/original.mp4" \
  --remake "/绝对路径/remake.mp4" \
  --instruction "把现代背景改为中国古代，保留剧情和镜头顺序" \
  --prepare-only
```

完整评测，并加入 ASR/OCR：

```bash
cp .env.example .env
# 在 .env 中填入 API_KEY、API_BASE_URL、MODEL、ASR_MODEL 和 OCR_MODEL
drama-eval run \
  --original "/绝对路径/original.mp4" \
  --remake "/绝对路径/remake.mp4" \
  --instruction "把现代背景改为中国古代，保留剧情和镜头顺序" \
  --with-asr \
  --with-ocr
```

也可以只开启其中一种能力。`--prepare-only` 与 `--with-asr/--with-ocr` 搭配时，会生成结构化证据文件，但不会运行最后的综合 Judge。

将机器结果与人工黄金答案比较：

```bash
drama-eval compare \
  --machine examples/machine_result.example.json \
  --gold examples/gold_sample.example.json
```

比较结果会给出逐维度绝对误差、平均绝对误差、完全一致率、相差不超过 1 分的比例，以及最终上线判断是否一致。这一步就是用黄金集验证“机器评委”是否接近人工标准。

## 这版 Agent 的工作流

```text
原视频 + 用户指令 + 复刻视频
             ↓
       镜头变化检测
             ↓
每镜头首/中/尾帧 + 长镜头补帧
       ↙                 ↘
ASR 台词及时间戳       OCR 画面文字
       ↘                 ↙
  挂载到对应镜头和证据帧
             ↓
多模态 Judge 按 Rubric 分维度评测
             ↓
得分 + 理由 + 证据帧 + 是否通过
```

## Git / GitHub 练习路线

本项目会先在本地 Git 仓库建立 `main`。推荐这样体验协作：

1. 从 `main` 创建 `feature/asr-ocr` 分支；
2. 在功能分支加入 ASR/OCR；
3. 提交 commit；
4. 推送到 GitHub；
5. 创建 Pull Request；
6. 查看 diff 后合并回 `main`；
7. 本地切回 `main` 并拉取合并结果。

注意：Git 是本地版本管理；GitHub 是托管远程仓库和协作的平台；“合一下代码”通常指将功能分支通过 Pull Request 合并进 `main`。

## 当前限制与下一步

- 当前已支持可选 ASR 及时间戳，用于辅助剧情和台词评测；
- 当前已支持可选 OCR，用于辅助字幕和画面文字评测；
- 定位动态片段，必要时让模型查看 3–10 秒视频片段；
- 加入人工黄金集批跑与机评/人评一致性统计；
- 增加低置信度与随机抽检的人评回流。
