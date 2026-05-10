# 手动 AI 模式接口文档

## 概述

手动 AI 模式允许用户在获取字幕后暂停任务，手动复制提示词到其他 AI 工具，导入结果后继续执行任务。

## 接口列表

### 1. 获取手动任务

**接口地址：** `GET /api/manual_task`

**功能说明：** 获取最早的手动暂停任务（用户不知道 task_id，所以返回最早的一个）

**请求参数：** 无

**响应示例：**

```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "task_id": "0c800fa6-c5e7-4c5d-aae3-8d706048ef46",
    "status": "MANUAL_PENDING",
    "title": "视频标题",
    "video_url": "https://www.bilibili.com/video/BV1xxx",
    "platform": "bilibili",
    "transcript": "完整的字幕文本内容...",
    "prompt": "请根据以下视频内容生成笔记...\n\n视频标题：xxx\n时间戳：[0.00 - 5.00]: 第一段文字...",
    "options": {
      "format": ["toc", "link", "screenshot"],
      "style": "detailed",
      "screenshot": true,
      "link": true,
      "extras": ""
    }
  }
}
```

**curl 示例：**

```bash
curl -X GET http://localhost:8483/api/manual_task
```

**PowerShell 示例：**

```powershell
Invoke-RestMethod -Uri 'http://localhost:8483/api/manual_task' -Method Get
```

**响应字段说明：**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| task_id | string | 任务唯一标识符 |
| status | string | 任务状态，始终为 `MANUAL_PENDING` |
| title | string | 视频标题 |
| video_url | string | 视频URL |
| platform | string | 平台名称（如 bilibili、youtube） |
| transcript | string | 完整字幕文本 |
| prompt | string | 生成的提示词，可直接复制到 AI 工具使用 |
| options | object | 用户选择的生成选项 |
| options.format | array | 格式选项列表 |
| options.style | string | 笔记风格 |
| options.screenshot | boolean | 是否插入截图 |
| options.link | boolean | 是否插入链接 |
| options.extras | string | 额外参数 |

**错误响应：**

```json
{
  "code": 404,
  "msg": "没有等待手动导入的任务",
  "data": null
}
```

---

### 2. 继续执行手动任务

**接口地址：** `POST /api/manual_task/{task_id}/continue`

**功能说明：** 导入大模型生成的内容，继续执行暂停的任务

**路径参数：**

| 参数名 | 类型 | 说明 |
|--------|------|------|
| task_id | string | 任务ID，从上一个接口获取 |

**请求体：**

```json
{
  "ai_generated_content": "# 视频笔记\n\n## 目录\n- 内容1\n- 内容2\n\n## 正文..."
}
```

| 字段名 | 类型 | 说明 |
|--------|------|------|
| ai_generated_content | string | 大模型（AI）生成的内容，通常是 Markdown 格式 |

**响应示例：**

```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "task_id": "0c800fa6-c5e7-4c5d-aae3-8d706048ef46",
    "status": "SUCCESS",
    "markdown": "> 来源链接：https://www.bilibili.com/video/BV1xxx\n\n# 视频笔记\n\n## 目录\n- 内容1\n- 内容2\n\n## 正文...",
    "title": "视频标题"
  }
}
```

**响应字段说明：**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| task_id | string | 任务唯一标识符 |
| status | string | 执行状态，成功为 `SUCCESS` |
| markdown | string | 处理后的笔记内容（已插入视频来源链接） |
| title | string | 视频标题 |

**curl 示例：**

```bash
curl -X POST http://localhost:8483/api/manual_task/{task_id}/continue \
  -H "Content-Type: application/json" \
  -d '{"ai_generated_content": "# 视频笔记\n\n## 目录\n- 内容1\n- 内容2\n\n## 正文\n这是测试内容。"}'
```

**PowerShell 示例：**

```powershell
$body = @{
    ai_generated_content = "# 视频笔记`n`n## 目录`n- 内容1`n- 内容2`n`n## 正文`n这是测试内容。"
} | ConvertTo-Json

Invoke-RestMethod -Uri 'http://localhost:8483/api/manual_task/{task_id}/continue' `
  -Method Post `
  -ContentType 'application/json' `
  -Body $body
```

**错误响应：**

```json
{
  "code": 500,
  "msg": "继续执行手动任务失败: <具体错误信息>"
}
```

---

## 使用流程

1. **启动手动 AI 模式**
   - 用户在前端勾选"手动 AI 模式"复选框
   - 填写视频URL和其他选项后提交

2. **任务暂停**
   - 系统获取字幕后自动暂停任务
   - 状态变为 `MANUAL_PENDING`

3. **获取任务信息**
   - 调用 `GET /api/manual_task` 获取任务ID、提示词和字幕

4. **手动生成内容**
   - 将提示词复制到其他 AI 工具（如 ChatGPT、Claude 等）
   - 让 AI 根据提示词生成笔记内容

5. **导入 AI 结果**
   - 调用 `POST /api/manual_task/{task_id}/continue`
   - 将 AI 生成的 Markdown 内容作为请求体传入

6. **任务完成**
   - 系统自动处理截图和链接插入
   - 返回完整的笔记内容
   - 任务状态变为 `SUCCESS`

## 数据存储

手动任务信息存储在 `{NOTE_OUTPUT_DIR}/{task_id}.manual_task.json` 文件中，包括：
- 任务ID
- 视频URL和平台
- 字幕内容（完整文本和时间戳）
- 生成的提示词
- 用户选择的选项

## 注意事项

1. 提示词中的 `segment_text` 字段包含带时间戳的字幕信息，格式为 `[开始时间 - 结束时间]: 文字内容`

2. 导入的 `ai_generated_content` 应该是 Markdown 格式的文本

3. 系统会自动处理截图标记（`Screenshot`）和时间戳链接标记

4. 如果任务失败，系统会返回错误信息，可以检查后端日志获取详细原因

/ralph-loop 以技能 manual-ai-auto-processor 为基础，每轮完成后等待 5 秒，反复执行，直到我取消。