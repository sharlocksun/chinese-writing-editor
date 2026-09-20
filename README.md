# Chinese Writing Editor

面向中文论文、学术报告、项目计划书和一般文章的自然写作与编辑 skill。它通过识别空话、机械结构、模板词群和聊天机器人残留来改善表达，同时保护事实、数据、引文、术语、条件和不确定性。

这不是 AI 检测器，也不承诺降低某个检测平台的分数。目标是让文字符合具体文体、读者和写作目的。

## 主要特点

- 区分论文、报告、计划书、技术说明和一般写作，不把所有文本改成同一种口语风格。
- 支持起草、默认改写、原位修改、结构重写和只标问题。
- 不编造人物、样本、数据、年份、案例、文献或个人经历。
- 保留核心术语，不为了避免重复而制造概念漂移。
- 对三项列举、连接词、被动语态和破折号等弱信号结合上下文判断，不机械禁用。
- 按任务边界区分局部编辑与全文一致性编辑，不用固定字数机械划分长短。
- 完整论文、报告和计划书可维护术语、事实与论点的一致性；需要分批时按章节处理并做全文复核。
- 附带只读长文审查脚本，用于定位短语聚集、重复开头、句长过齐和重复句。

## 安装

在 Codex 中调用 skill installer：

```text
$skill-installer https://github.com/sharlocksun/chinese-writing-editor
```

安装后可显式调用：

```text
$chinese-writing-editor 修改下面这段硕士论文，保留事实、引文和专业术语。
```

也可以指定范围：

```text
$chinese-writing-editor 保留段落结构，只修改句内表达。
```

```text
$chinese-writing-editor 只标问题，不改写正文。
```

## 文件结构

```text
chinese-writing-editor/
├── SKILL.md
├── agents/openai.yaml
├── references/
│   ├── examples.md
│   ├── long-form-consistency.md
│   ├── patterns-zh.md
│   ├── research-basis.md
│   └── scenes.md
└── scripts/audit_zh_style.py
```

- [SKILL.md](SKILL.md)：入口规则和编辑工作流。
- [patterns-zh.md](references/patterns-zh.md)：中文模板模式及判断边界。
- [scenes.md](references/scenes.md)：论文、报告、计划书等场景指南。
- [long-form-consistency.md](references/long-form-consistency.md)：完整文档的术语、事实、论点和跨章节一致性协议。
- [examples.md](references/examples.md)：保真改写与不应修改的示例。
- [research-basis.md](references/research-basis.md)：相关项目的研究比较与规则取舍。

## 完整文档一致性

是否启用全文一致性模式由任务边界决定，不设固定字数门槛。一篇完整的 7000 字期刊论文需要核对摘要、正文和结论；一组更长但彼此独立的材料则可以分别处理。字数只决定能否一次安全处理以及是否需要按章节分批。

能够完整通读的论文采用轻量协议，只记录容易漂移的术语、事实和中心论点。需要跨批次处理的学位论文或大型报告采用分段协议，维护精简的全局状态，并在全部章节完成后进行全文整合审查。

## 长文审查

审查纯文本或 Markdown 文件：

```bash
python scripts/audit_zh_style.py <文件路径>
```

使用 `--json` 输出结构化结果。脚本只报告编辑候选，不判断文本是否由 AI 生成，也不会修改原文件。
