'use client'

import { useEffect, useState } from 'react'
import { Copy, Download, BrainCircuit, MessageSquare, Wand2, RefreshCw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger } from '@/components/ui/select'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import { Badge } from '@/components/ui/badge'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { toast } from 'react-hot-toast'
import { useTaskStore } from '@/store/taskStore'

interface VersionNote {
  ver_id: string
  model_name?: string
  style?: string
  created_at?: string
}

interface NoteHeaderProps {
  currentTask?: {
    markdown: VersionNote[] | string
    id: string
    formData: {
      video_url: string
      style: string
    }
    audioMeta?: {
      title: string
    }
  }
  isMultiVersion: boolean
  currentVerId: string
  setCurrentVerId: (id: string) => void
  modelName: string
  style: string
  noteStyles: { value: string; label: string }[]
  onCopy: () => void
  onDownload: () => void
  createAt?: string | Date
  setShowTranscribe: (show: boolean) => void
  showChat?: false | 'half' | 'full'
  setShowChat?: (mode: false | 'half' | 'full') => void
  viewMode: 'map' | 'preview'
  setViewMode: (mode: 'map' | 'preview') => void
  showTranscribe: boolean
}

export function MarkdownHeader({
  currentTask,
  isMultiVersion,
  currentVerId,
  setCurrentVerId,
  modelName,
  style,
  noteStyles,
  onCopy,
  onDownload,
  createAt,
  showTranscribe,
  setShowTranscribe,
  showChat,
  setShowChat,
  viewMode,
  setViewMode,
}: NoteHeaderProps) {
  const [copied, setCopied] = useState(false)
  const [showPromptDialog, setShowPromptDialog] = useState(false)
  const [prompt, setPrompt] = useState('')
  const [customMarkdown, setCustomMarkdown] = useState('')
  const [isGenerating, setIsGenerating] = useState(false)
  const [isReplacing, setIsReplacing] = useState(false)
  const [isRefreshing, setIsRefreshing] = useState(false)
  const updateTaskContent = useTaskStore.getState().updateTaskContent

  useEffect(() => {
    let timer: NodeJS.Timeout
    if (copied) {
      timer = setTimeout(() => setCopied(false), 2000)
    }
    return () => clearTimeout(timer)
  }, [copied])

  const handleCopy = () => {
    onCopy()
    setCopied(true)
  }

  // 生成提示词
  const handleGeneratePrompt = async () => {
    if (!currentTask?.id) return
    setIsGenerating(true)
    try {
      const response = await fetch('/api/generate_prompt', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          task_id: currentTask.id,
          title: currentTask.audioMeta?.title || '',
          tags: [],
          style: currentTask.formData.style || 'detailed',
          formats: ['link', 'summary'],
        }),
      })
      const result = await response.json()
      if (result.code === 0) {
        setPrompt(result.data.prompt)
        toast.success('提示词生成成功')
      } else {
        toast.error(result.msg || '生成失败')
      }
    } catch (error) {
      toast.error('生成提示词失败')
      console.error(error)
    } finally {
      setIsGenerating(false)
    }
  }

  // 复制提示词
  const handleCopyPrompt = async () => {
    if (!prompt) return
    try {
      await navigator.clipboard.writeText(prompt)
      toast.success('提示词已复制到剪贴板')
    } catch (error) {
      toast.error('复制失败')
    }
  }

  // 替换笔记内容
  const handleReplaceMarkdown = async () => {
    if (!currentTask?.id || !customMarkdown.trim()) {
      toast.error('请输入内容')
      return
    }
    setIsReplacing(true)
    try {
      const response = await fetch('/api/replace_markdown', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          task_id: currentTask.id,
          markdown: customMarkdown.trim(),
        }),
      })
      const result = await response.json()
      if (result.code === 0) {
        toast.success('笔记替换成功')
        setCustomMarkdown('')
        setShowPromptDialog(false)
        // 更新本地任务状态（不传入status，避免被过滤）
        updateTaskContent(currentTask.id, {
          markdown: customMarkdown.trim(),
        })
      } else {
        toast.error(result.msg || '替换失败')
      }
    } catch (error) {
      toast.error('替换笔记失败')
      console.error(error)
    } finally {
      setIsReplacing(false)
    }
  }

  // 刷新任务内容（从后端重新获取）
  const handleRefreshTask = async () => {
    if (!currentTask?.id) return
    setIsRefreshing(true)
    try {
      const response = await fetch(`/api/task_status/${currentTask.id}`)
      const result = await response.json()
      if (result.code === 0 && result.data.status === 'SUCCESS') {
        const { markdown, transcript, audio_meta } = result.data.result
        updateTaskContent(currentTask.id, {
          status: 'SUCCESS',
          markdown,
          transcript,
          audioMeta: audio_meta,
        })
        toast.success('笔记已刷新')
      } else {
        toast.error(result.msg || '刷新失败')
      }
    } catch (error) {
      toast.error('刷新笔记失败')
      console.error(error)
    } finally {
      setIsRefreshing(false)
    }
  }

  const styleName = noteStyles.find(v => v.value === style)?.label || style

  const reversedMarkdown: VersionNote[] = Array.isArray(currentTask?.markdown)
    ? [...currentTask!.markdown].reverse()
    : []

  const formatDate = (date: string | Date | undefined) => {
    if (!date) return ''
    const d = typeof date === 'string' ? new Date(date) : date
    if (isNaN(d.getTime())) return ''
    return d
      .toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
      .replace(/\//g, '-')
  }

  return (
    <div className="sticky top-0 z-10 flex flex-wrap items-center justify-between gap-3 border-b bg-white/95 px-4 py-2 backdrop-blur-sm">
      {/* 左侧区域：版本 + 标签 + 创建时间 */}
      <div className="flex flex-wrap items-center gap-3">
        {isMultiVersion && (
          <Select value={currentVerId} onValueChange={setCurrentVerId}>
            <SelectTrigger className="h-8 w-[160px] text-sm">
              <div className="flex items-center">
                {(() => {
                  const idx = currentTask?.markdown.findIndex(v => v.ver_id === currentVerId)
                  return idx !== -1 ? `版本（${currentVerId.slice(-6)}）` : ''
                })()}
              </div>
            </SelectTrigger>

            <SelectContent>
              {(currentTask?.markdown || []).map((v, idx) => {
                const shortId = v.ver_id.slice(-6)
                return (
                  <SelectItem key={v.ver_id} value={v.ver_id}>
                    {`版本（${shortId}）`}
                  </SelectItem>
                )
              })}
            </SelectContent>
          </Select>
        )}

        <Badge variant="secondary" className="bg-pink-100 text-pink-700 hover:bg-pink-200">
          {modelName}
        </Badge>
        <Badge variant="secondary" className="bg-cyan-100 text-cyan-700 hover:bg-cyan-200">
          {styleName}
        </Badge>

        {createAt && (
          <div className="text-muted-foreground text-sm">创建时间: {formatDate(createAt)}</div>
        )}
      </div>

      {/* 右侧操作按钮 */}
      <div className="flex items-center gap-1">
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                onClick={() => {
                  setViewMode(viewMode == 'preview' ? 'map' : 'preview')
                }}
                variant="ghost"
                size="sm"
                className="h-8 px-2"
              >
                <BrainCircuit className="mr-1.5 h-4 w-4" />
                <span className="text-sm">{viewMode == 'preview' ? '思维导图' : 'markdown'}</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>思维导图</TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button onClick={handleCopy} variant="ghost" size="sm" className="h-8 px-2">
                <Copy className="mr-1.5 h-4 w-4" />
                <span className="text-sm">{copied ? '已复制' : '复制'}</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>复制内容</TooltipContent>
          </Tooltip>
        </TooltipProvider>

        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button onClick={onDownload} variant="ghost" size="sm" className="h-8 px-2">
                <Download className="mr-1.5 h-4 w-4" />
                <span className="text-sm">导出 Markdown</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>下载为 Markdown 文件</TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                onClick={() => {
                  setShowTranscribe(!showTranscribe)
                }}
                variant="ghost"
                size="sm"
                className="h-8 px-2"
              >
                {/*<Download className="mr-1.5 h-4 w-4" />*/}
                <span className="text-sm">原文参照</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>原文参照</TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <Button
                onClick={handleRefreshTask}
                variant="ghost"
                size="sm"
                className="h-8 px-2"
                disabled={isRefreshing}
              >
                <RefreshCw className={`mr-1.5 h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
                <span className="text-sm">刷新</span>
              </Button>
            </TooltipTrigger>
            <TooltipContent>从服务器刷新笔记</TooltipContent>
          </Tooltip>
        </TooltipProvider>
        <Dialog open={showPromptDialog} onOpenChange={setShowPromptDialog}>
          <DialogTrigger asChild>
            <Button variant="ghost" size="sm" className="h-8 px-2">
              <Wand2 className="mr-1.5 h-4 w-4" />
              <span className="text-sm">手动调用AI</span>
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-4xl max-h-[80vh]">
            <DialogHeader>
              <DialogTitle>手动调用大模型</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              {/* 提示词生成区域 */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium">生成的提示词</label>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={handleGeneratePrompt}
                      disabled={isGenerating}
                    >
                      {isGenerating ? '生成中...' : '生成提示词'}
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={handleCopyPrompt}
                      disabled={!prompt}
                    >
                      <Copy className="mr-1 h-3 w-3" />
                      复制
                    </Button>
                  </div>
                </div>
                <Textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="点击上方按钮生成提示词，然后复制到大模型中..."
                  className="h-40 font-mono text-xs"
                  disabled={isGenerating}
                />
              </div>

              {/* 分割线 */}
              <div className="border-t border-muted" />

              {/* 结果输入区域 */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium">
                    将大模型返回的结果粘贴到这里
                  </label>
                  <Button
                    size="sm"
                    onClick={handleReplaceMarkdown}
                    disabled={isReplacing || !customMarkdown.trim()}
                  >
                    {isReplacing ? '替换中...' : '替换笔记'}
                  </Button>
                </div>
                <Textarea
                  value={customMarkdown}
                  onChange={(e) => setCustomMarkdown(e.target.value)}
                  placeholder="将大模型返回的Markdown内容粘贴到这里..."
                  className="h-40 font-mono text-xs"
                  disabled={isReplacing}
                />
              </div>

              {/* 说明 */}
              <div className="bg-muted/50 rounded-lg p-3 text-xs text-muted-foreground">
                <p className="font-medium mb-1">使用说明：</p>
                <ol className="list-decimal list-inside space-y-1">
                  <li>点击「生成提示词」按钮生成用于调用大模型的提示词</li>
                  <li>复制提示词到你选择的大模型中（如 ChatGPT、Claude 等）</li>
                  <li>将大模型返回的结果粘贴到下方输入框</li>
                  <li>点击「替换笔记」按钮将结果保存到当前笔记中</li>
                </ol>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {setShowChat && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  onClick={() => setShowChat(showChat ? false : 'half')}
                  variant={showChat ? 'default' : 'ghost'}
                  size="sm"
                  className="h-8 px-2"
                >
                  <MessageSquare className="mr-1.5 h-4 w-4" />
                  <span className="text-sm">AI 问答</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent>基于笔记内容的 AI 问答</TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
      </div>
    </div>
  )
}
