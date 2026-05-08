# BiliNote 手动调用AI功能改造总结

## 目录

1. [功能概述](#功能概述)
2. [修改内容总结](#修改内容总结)
   - [跳过AI功能](#跳过ai功能)
   - [手动调用AI功能](#手动调用ai功能)
   - [修复组件渲染问题](#修复组件渲染问题)
3. [Git分支策略](#git分支策略)
4. [改造步骤](#改造步骤)

---

## 功能概述

本次改造实现了以下核心功能：

1. **跳过AI生成**：用户可以选择只保存字幕，跳过LLM笔记生成
2. **手动调用AI**：在跳过AI模式下，用户可以生成提示词，手动调用外部大模型，然后将结果替换到笔记中
3. **刷新功能**：提供手动刷新按钮，从后端重新获取笔记内容

---

## 修改内容总结

### 一、跳过AI功能

#### 1. 后端修改

**文件**: `backend/app/routers/note.py`

**修改内容**:
- 在 `VideoRequest` 模型中添加 `skip_ai: Optional[bool] = False` 参数
- 将 `model_name`、`provider_id`、`style` 改为可选参数
- 在验证逻辑中跳过模型检查当 `skip_ai=True`

**代码位置**: 约第34行

**文件**: `backend/app/services/note.py`

**修改内容**:
- 在 `generate()` 方法中处理 `skip_ai` 标志
- 当 `skip_ai=True` 时，直接使用字幕内容而不调用LLM

**代码位置**: 约第15-636行

**文件**: `backend/app/downloaders/bilibili_downloader.py`

**修改内容**:
- 在 `download()` 方法中添加 `skip_download` 参数
- 当 `skip_download=True` 时，只提取元数据而不下载视频

**代码位置**: 约第48行

#### 2. 前端修改

**文件**: `BillNote_frontend/src/pages/HomePage/components/NoteForm.tsx`

**修改内容**:
- 添加「只保存字幕（跳过AI总结）」复选框
- 当勾选时禁用AI相关选项

---

### 二、手动调用AI功能

#### 1. 后端修改

**文件**: `backend/app/routers/note.py`

**修改内容**:
- 添加 `GeneratePromptRequest` 和 `ReplaceMarkdownRequest` 模型
- 添加 `/generate_prompt` 接口：根据任务ID生成LLM提示词
- 添加 `/replace_markdown` 接口：将手动调用结果替换到笔记中

**代码位置**: 约第328-450行

**关键实现**:
- `/generate_prompt` 读取字幕文件，使用 `prompt_builder.py` 生成完整提示词
- `/replace_markdown` 更新 `.json` 和 `_markdown.md` 文件，确保刷新时能获取到最新内容

#### 2. 前端修改

**文件**: `BillNote_frontend/src/pages/HomePage/components/MarkdownHeader.tsx`

**修改内容**:
- 添加「手动调用AI」按钮和对话框
- 对话框包含提示词生成、复制功能
- 对话框包含Markdown内容替换功能
- 添加「刷新」按钮，从后端重新获取任务内容

**代码位置**: 约第297-380行（对话框），约第327-343行（刷新按钮）

---

### 三、修复组件渲染问题

**文件**: `BillNote_frontend/src/pages/HomePage/components/MarkdownViewer.tsx`

**修改内容**:
- 在 `useEffect` 依赖数组中添加 `currentTask?.markdown`
- 确保当markdown内容更新时组件能正确重新渲染

**代码位置**: 约第311行

---

## Git分支策略

建议按照以下分支结构管理：

```
main
└── pro
    ├── feature/skip-ai           # 跳过AI功能
    ├── feature/manual-ai-call    # 手动调用AI功能
    └── bugfix/component-render   # 组件渲染修复
```

### 提交建议

#### 1. 跳过AI功能 (feature/skip-ai)
```bash
git checkout -b feature/skip-ai pro
git add backend/app/routers/note.py
git add backend/app/services/note.py
git add backend/app/downloaders/bilibili_downloader.py
git add BillNote_frontend/src/pages/HomePage/components/NoteForm.tsx
git commit -m "feat: 添加跳过AI功能，支持只保存字幕"
git push origin feature/skip-ai
```

#### 2. 手动调用AI功能 (feature/manual-ai-call)
```bash
git checkout -b feature/manual-ai-call pro
git add backend/app/routers/note.py
git add BillNote_frontend/src/pages/HomePage/components/MarkdownHeader.tsx
git commit -m "feat: 添加手动调用AI功能，支持生成提示词和替换笔记"
git push origin feature/manual-ai-call
```

#### 3. 组件渲染修复 (bugfix/component-render)
```bash
git checkout -b bugfix/component-render pro
git add BillNote_frontend/src/pages/HomePage/components/MarkdownViewer.tsx
git commit -m "fix: 修复MarkdownViewer组件不重新渲染问题"
git push origin bugfix/component-render
```

---

## 改造步骤

### 步骤1: 实现跳过AI功能

1. 修改 `backend/app/routers/note.py`
   - 在 `VideoRequest` 添加 `skip_ai` 参数
   - 修改验证逻辑

2. 修改 `backend/app/services/note.py`
   - 在 `generate()` 方法中处理 `skip_ai` 标志

3. 修改 `backend/app/downloaders/bilibili_downloader.py`
   - 添加 `skip_download` 参数

4. 修改 `BillNote_frontend/src/pages/HomePage/components/NoteForm.tsx`
   - 添加跳过AI复选框

### 步骤2: 实现手动调用AI功能

1. 修改 `backend/app/routers/note.py`
   - 添加 `GeneratePromptRequest` 和 `ReplaceMarkdownRequest` 模型
   - 实现 `/generate_prompt` 接口
   - 实现 `/replace_markdown` 接口（注意要更新 `.json` 文件）

2. 修改 `BillNote_frontend/src/pages/HomePage/components/MarkdownHeader.tsx`
   - 添加手动调用AI对话框
   - 添加刷新按钮

### 步骤3: 修复组件渲染问题

1. 修改 `BillNote_frontend/src/pages/HomePage/components/MarkdownViewer.tsx`
   - 更新 `useEffect` 依赖数组

---

## 注意事项

1. **后端接口兼容性**: `/replace_markdown` 接口必须更新 `.json` 文件，否则刷新时无法获取最新内容
2. **前端状态更新**: 调用 `updateTaskContent` 时不要传入 `status: 'SUCCESS'`，否则会被过滤
3. **依赖数组**: 确保 `MarkdownViewer` 的 `useEffect` 依赖包含 `currentTask?.markdown`
4. **样式导入**: 确保 `MarkdownHeader` 导入了 `RefreshCw` 和 `Wand2` 图标

---

## 使用流程

1. 勾选「只保存字幕」选项生成笔记（跳过AI）
2. 在笔记页面点击「手动调用AI」按钮
3. 点击「生成提示词」生成用于调用大模型的提示词
4. 复制提示词到外部大模型（如 ChatGPT、Claude 等）
5. 将大模型返回的 Markdown 结果粘贴到输入框
6. 点击「替换笔记」按钮将结果保存到当前笔记中
7. 如果页面没有自动更新，点击「刷新」按钮手动从服务器获取

---

**文档版本**: v1.0  
**创建日期**: 2026-05-08  
**适用分支**: pro