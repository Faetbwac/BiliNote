---
name: manual-ai-auto-processor
description: 自动获取手动AI任务，生成笔记并提交。搭配 opencode-ralph-loop 循环执行。
version: 1.0.5
parameters:
  - name: api_base_url
    type: string
    description: 后端 API 基础地址，从 .env 读取 VITE_API_BASE_URL 或默认 http://127.0.0.1:8483
    default: ${VITE_API_BASE_URL:-http://127.0.0.1:8483}
---

# 手动 AI 自动笔记处理器

## 功能
本技能用于处理前端提交的"手动 AI 模式"暂停任务。
它调用后端接口获取最早的任务，提取 `prompt`，让你（AI）生成 Markdown 笔记，然后自动提交结果。

**重要：每个任务都是独立的！必须严格根据该任务专属的 prompt 生成笔记，不使用任何旧笔记模板。**

## 执行步骤（单次）

### 1. 获取任务
使用 Python 发送 GET 请求，并正确处理 UTF-8 编码：
```python
import sys
import io
import requests
import json

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

resp = requests.get('{api_base_url}/api/manual_task')
data = resp.json()

if data.get('code') == 0 and data.get('data'):
    task_id = data['data']['task_id']
    title = data['data'].get('title', '')
    prompt = data['data']['prompt']
    print(f'获取任务成功: {task_id}')
    print(f'标题: {title}')

    with open(r'C:\Users\shiyige\AppData\Local\Temp\opencode\task_current.json', 'w', encoding='utf-8') as f:
        json.dump({'task_id': task_id, 'prompt': prompt, 'title': title}, f, ensure_ascii=False, indent=2)
else:
    print("无待处理任务")
```

### 2. 生成笔记（关键步骤）

**必须严格遵循以下规则：**

1. **立即读取该任务专属 prompt**：从保存的文件中读取，不要使用之前保存的任何旧 prompt
2. **分析 prompt 中的所有视频分段**：提取所有 `[时间 - 时间]: 内容` 格式的分段
3. **生成详细风格的笔记**：不能简略，要像保姆级教程那样详细记录每个步骤
4. **不遗漏任何重要细节**：包括具体用量、火候、时间、温度等
5. **包含 prompt 要求的所有功能**：
   - 目录（自动生成 ## 级标题目录）
   - 原片跳转（使用 `*Content-[mm:ss]` 格式）
   - 原片截图（如有截图，使用 `*Screenshot-[mm:ss]` 格式）
   - AI 总结（在笔记末尾以 `## AI 总结` 为二级标题）

**禁止：**
- 不使用任何之前保存的笔记模板
- 不复制粘贴之前生成的笔记
- 不遗漏视频分段中的重要内容

### 3. 提交结果
```python
import requests

with open(r'C:\Users\shiyige\AppData\Local\Temp\opencode\notes.json', 'r', encoding='utf-8') as f:
    content = f.read()

with open(r'C:\Users\shiyige\AppData\Local\Temp\opencode\task_current.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
task_id = data['task_id']

resp = requests.post(
    '{api_base_url}/api/manual_task/{task_id}/continue',
    json={'ai_generated_content': content}
)
result = resp.json()
if result.get('code') == 0:
    print(f'SUCCESS - 任务 {task_id} 处理完成!')
else:
    print(f'FAILED - {result.get("msg", "未知错误")}')
```

## 重要规则
- **必须使用 Python 发送 HTTP 请求**，避免 curl 在 Windows 下的编码问题
- **在 Python 开头设置 UTF-8 编码**，确保中文正确显示
- **每个任务都是独立的**，必须严格读取并遵循该任务专属的 prompt
- **生成详细风格的笔记**，像保姆级教程那样记录每个步骤的细节
- **不遗漏任何重要内容**，包括具体用量、火候、时间、温度等
- 每轮完成后等待 5 秒再继续下一轮