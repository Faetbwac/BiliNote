# app/routers/note.py
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, BackgroundTasks, UploadFile, File
from pydantic import BaseModel, validator, field_validator
from dataclasses import asdict

from app.db.video_task_dao import get_task_by_video
from app.enmus.exception import NoteErrorEnum
from app.enmus.note_enums import DownloadQuality
from app.exceptions.note import NoteError
from app.services.note import NoteGenerator, logger
from app.services.task_serial_executor import task_serial_executor
from app.utils.response import ResponseWrapper as R
from app.utils.url_parser import extract_video_id
from app.validators.video_url_validator import is_supported_video_url
from app.gpt.prompt_builder import generate_base_prompt
from app.gpt.prompt import BASE_PROMPT, AI_SUM, SCREENSHOT, LINK, MERGE_PROMPT
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
import httpx
from app.enmus.task_status_enums import TaskStatus

# from app.services.downloader import download_raw_audio
# from app.services.whisperer import transcribe_audio

router = APIRouter()


class RecordRequest(BaseModel):
    video_id: str
    platform: str


class VideoRequest(BaseModel):
    video_url: str
    platform: str
    quality: DownloadQuality
    screenshot: Optional[bool] = False
    link: Optional[bool] = False
    model_name: Optional[str] = None
    provider_id: Optional[str] = None
    task_id: Optional[str] = None
    format: Optional[List[str]] = None
    style: Optional[str] = None
    extras: Optional[str]=None
    video_understanding: Optional[bool] = False
    video_interval: Optional[int] = 0
    grid_size: Optional[List[int]] = None
    skip_ai: Optional[bool] = False
    manual_ai: Optional[bool] = False
    # 客户端（如浏览器插件）已经在用户浏览器里抓到字幕，直接传给后端复用，
    # 跳过 download_subtitles 和音频转写。形如：
    #   {"language": "zh", "full_text": "...", "segments": [{"start","end","text"}, ...]}
    prefetched_transcript: Optional[dict] = None

    @field_validator("video_url")
    def validate_supported_url(cls, v):
        url = str(v)
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https"):
            # 是网络链接，继续用原有平台校验
            if not is_supported_video_url(url):
                raise NoteError(code=NoteErrorEnum.PLATFORM_NOT_SUPPORTED.code,
                                message=NoteErrorEnum.PLATFORM_NOT_SUPPORTED.message)

        return v


NOTE_OUTPUT_DIR = os.getenv("NOTE_OUTPUT_DIR", "note_results")
UPLOAD_DIR = "uploads"


def save_note_to_file(task_id: str, note):
    os.makedirs(NOTE_OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(NOTE_OUTPUT_DIR, f"{task_id}.json"), "w", encoding="utf-8") as f:
        json.dump(asdict(note), f, ensure_ascii=False, indent=2)


def _persist_prefetched_transcript(task_id: str, transcript: dict) -> None:
    """把客户端预取的字幕写到 NoteGenerator 期望的转写缓存文件里。

    NoteGenerator.generate 会优先读 <task_id>_transcript.json，命中即跳过 download_subtitles
    与音频转写流程。要求字段：language(可空)/full_text/segments[{start,end,text}]
    """
    segments = transcript.get("segments") or []
    cleaned_segments = []
    for s in segments:
        text = (s.get("text") or "").strip()
        if not text:
            continue
        cleaned_segments.append({
            "start": float(s.get("start", 0)),
            "end": float(s.get("end", 0)),
            "text": text,
        })
    if not cleaned_segments:
        raise ValueError("prefetched_transcript 没有可用的 segments")

    full_text = transcript.get("full_text") or " ".join(s["text"] for s in cleaned_segments)
    payload = {
        "language": transcript.get("language") or "zh",
        "full_text": full_text,
        "segments": cleaned_segments,
    }

    os.makedirs(NOTE_OUTPUT_DIR, exist_ok=True)
    target = os.path.join(NOTE_OUTPUT_DIR, f"{task_id}_transcript.json")
    with open(target, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info(f"已写入客户端预取字幕缓存: {target} ({len(cleaned_segments)} 段)")


def run_note_task(task_id: str, video_url: str, platform: str, quality: DownloadQuality,
                  link: bool = False, screenshot: bool = False, model_name: str = None, provider_id: str = None,
                  _format: List[str] = None, style: str = None, extras: str = None, video_understanding: bool = False,
                  video_interval=0, grid_size: List[int] = None, skip_ai: bool = False, manual_ai: bool = False
                  ):

    if not skip_ai and not manual_ai and (not model_name or not provider_id):
        raise HTTPException(status_code=400, detail="请选择模型和提供者")

    logger.info(f"run_note_task 接收参数: manual_ai={manual_ai}, skip_ai={skip_ai}, _format={_format}")

    def _execute_note_task():
        if skip_ai:
            return NoteGenerator().generate(
                video_url=video_url,
                platform=platform,
                quality=quality,
                task_id=task_id,
                model_name=None,
                provider_id=None,
                link=link,
                _format=_format,
                style=None,
                extras=None,
                screenshot=screenshot,
                video_understanding=video_understanding,
                video_interval=video_interval,
                grid_size=grid_size,
                skip_ai=True,
                manual_ai=manual_ai,
            )
        return NoteGenerator().generate(
            video_url=video_url,
            platform=platform,
            quality=quality,
            task_id=task_id,
            model_name=model_name,
            provider_id=provider_id,
            link=link,
            _format=_format,
            style=style,
            extras=extras,
            screenshot=screenshot,
            video_understanding=video_understanding,
            video_interval=video_interval,
            grid_size=grid_size,
            manual_ai=manual_ai,
        )

    logger.info(f"任务进入执行队列 (task_id={task_id}, manual_ai={manual_ai}, skip_ai={skip_ai})")
    note = task_serial_executor.run(_execute_note_task)
    logger.info(f"Note generated: {task_id}")
    if not note or not note.markdown:
        logger.warning(f"任务 {task_id} 执行失败，跳过保存")
        return
    save_note_to_file(task_id, note)

    # 自动建立向量索引（用于 AI 问答），失败不影响笔记生成
    try:
        from app.services.vector_store import VectorStoreManager
        VectorStoreManager().index_task(task_id)
    except Exception as e:
        logger.warning(f"向量索引失败（不影响笔记）: {e}")


@router.post('/delete_task')
def delete_task(data: RecordRequest):
    try:
        # TODO: 待持久化完成
        # NoteGenerator().delete_note(video_id=data.video_id, platform=data.platform)
        return R.success(msg='删除成功')
    except Exception as e:
        return R.error(msg=e)


@router.post("/upload")
async def upload(file: UploadFile = File(...)):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    file_location = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_location, "wb+") as f:
        f.write(await file.read())

    # 假设你静态目录挂载了 /uploads
    return R.success({"url": f"/uploads/{file.filename}"})


@router.post("/generate_note")
def generate_note(data: VideoRequest, background_tasks: BackgroundTasks):
    try:

        video_id = extract_video_id(data.video_url, data.platform)
        # if not video_id:
        #     raise HTTPException(status_code=400, detail="无法提取视频 ID")
        # existing = get_task_by_video(video_id, data.platform)
        # if existing:
        #     return R.error(
        #         msg='笔记已生成，请勿重复发起',
        #
        #     )
        if data.task_id:
            # 如果传了task_id，说明是重试！
            task_id = data.task_id
            logger.info(f"重试模式，复用已有 task_id={task_id}")
        else:
            # 正常新建任务
            task_id = str(uuid.uuid4())

        # 统一先写入 PENDING，表示已进入队列等待串行执行
        NoteGenerator()._update_status(task_id, TaskStatus.PENDING)

        # 客户端已经抓好字幕的话，写到转写缓存文件，NoteGenerator 的 cache-hit 逻辑会直接用上
        if data.prefetched_transcript:
            try:
                _persist_prefetched_transcript(task_id, data.prefetched_transcript)
            except Exception as e:
                logger.warning(f"写入预取字幕失败 (task_id={task_id}): {e}")

        background_tasks.add_task(run_note_task, task_id, data.video_url, data.platform, data.quality, data.link,
                                  data.screenshot, data.model_name, data.provider_id, data.format, data.style,
                                  data.extras, data.video_understanding, data.video_interval, data.grid_size,
                                  data.skip_ai or False, data.manual_ai or False)
        return R.success({"task_id": task_id})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task_status/{task_id}")
def get_task_status(task_id: str):
    status_path = os.path.join(NOTE_OUTPUT_DIR, f"{task_id}.status.json")
    result_path = os.path.join(NOTE_OUTPUT_DIR, f"{task_id}.json")

    # 优先读状态文件
    if os.path.exists(status_path):
        with open(status_path, "r", encoding="utf-8") as f:
            status_content = json.load(f)

        status = status_content.get("status")
        message = status_content.get("message", "")

        if status == TaskStatus.SUCCESS.value:
            # 成功状态的话，继续读取最终笔记内容
            if os.path.exists(result_path):
                with open(result_path, "r", encoding="utf-8") as rf:
                    result_content = json.load(rf)
                return R.success({
                    "status": status,
                    "result": result_content,
                    "message": message,
                    "task_id": task_id
                })
            else:
                # 理论上不会出现，保险处理
                return R.success({
                    "status": TaskStatus.PENDING.value,
                    "message": "任务完成，但结果文件未找到",
                    "task_id": task_id
                })

        if status == TaskStatus.FAILED.value:
            return R.error(message or "任务失败", code=500)

        # 处理中状态
        return R.success({
            "status": status,
            "message": message,
            "task_id": task_id
        })

    # 没有状态文件，但有结果
    if os.path.exists(result_path):
        with open(result_path, "r", encoding="utf-8") as f:
            result_content = json.load(f)
        return R.success({
            "status": TaskStatus.SUCCESS.value,
            "result": result_content,
            "task_id": task_id
        })

    # 什么都没有，默认PENDING
    return R.success({
        "status": TaskStatus.PENDING.value,
        "message": "任务排队中",
        "task_id": task_id
    })


@router.get("/image_proxy")
async def image_proxy(request: Request, url: str):
    headers = {
        "Referer": "https://www.bilibili.com/",
        "User-Agent": request.headers.get("User-Agent", ""),
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=headers)

            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail="图片获取失败")

            content_type = resp.headers.get("Content-Type", "image/jpeg")
            return StreamingResponse(
                resp.aiter_bytes(),
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=86400",  #  缓存一天
                    "Content-Type": content_type,
                }
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class GeneratePromptRequest(BaseModel):
    """生成提示词请求"""
    task_id: str
    title: str = ""
    tags: list = []
    style: str = "detailed"
    formats: list = ["link", "summary"]


class ReplaceMarkdownRequest(BaseModel):
    """替换笔记内容请求"""
    task_id: str
    markdown: str


@router.post("/generate_prompt")
async def generate_prompt(request: GeneratePromptRequest):
    """
    根据任务ID生成用于手动调用大模型的提示词
    
    :param task_id: 任务ID
    :param title: 视频标题（可选）
    :param tags: 视频标签列表
    :param style: 笔记风格（minimal/detailed/academic/tutorial/xiaohongshu等）
    :param formats: 输出格式选项（link/screenshot/summary/toc）
    :return: 包含提示词的响应
    """
    try:
        # 读取字幕缓存文件
        transcript_file = Path(NOTE_OUTPUT_DIR) / f"{request.task_id}_transcript.json"
        if not transcript_file.exists():
            return R.fail(msg="字幕文件不存在，请先生成字幕")
        
        with open(transcript_file, 'r', encoding='utf-8') as f:
            transcript_data = json.load(f)
        
        # 构建分段文本（带时间戳）
        segments = transcript_data.get("segments", [])
        if not segments:
            return R.fail(msg="字幕内容为空")
        
        segment_text = ""
        for seg in segments:
            start = seg.get("start", 0)
            # 转换为 mm:ss 格式
            minutes = int(start // 60)
            seconds = int(start % 60)
            time_str = f"{minutes:02d}:{seconds:02d}"
            text = seg.get("text", "").strip()
            if text:
                segment_text += f"{time_str} - {text}\n\n"
        
        # 生成提示词
        prompt = generate_base_prompt(
            title=request.title or "未命名视频",
            segment_text=segment_text.strip(),
            tags=request.tags,
            _format=request.formats,
            style=request.style,
            extras=None
        )
        
        return R.success(data={
            "prompt": prompt,
            "task_id": request.task_id,
            "segment_count": len(segments),
            "prompt_length": len(prompt)
        })
    
    except Exception as e:
        logger.error(f"生成提示词失败: {e}")
        return R.fail(msg=f"生成提示词失败: {str(e)}")


@router.post("/replace_markdown")
async def replace_markdown(request: ReplaceMarkdownRequest):
    """
    将手动调用大模型的结果替换到笔记中
    
    :param task_id: 任务ID
    :param markdown: 大模型返回的Markdown内容
    :return: 替换结果
    """
    try:
        # 更新markdown缓存文件
        markdown_file = Path(NOTE_OUTPUT_DIR) / f"{request.task_id}_markdown.md"
        markdown_file.write_text(request.markdown, encoding="utf-8")
        
        # 更新.json结果文件（get_task_status读取的是这个文件）
        result_path = os.path.join(NOTE_OUTPUT_DIR, f"{request.task_id}.json")
        result_content = {
            "markdown": [{
                "ver_id": f"{request.task_id}-manual",
                "content": request.markdown,
                "style": "manual",
                "model_name": "manual",
                "created_at": datetime.now().isoformat()
            }],
            "transcript": {"full_text": "", "language": "", "raw": {}, "segments": []},
            "audio_meta": {"title": "手动替换", "platform": "", "video_id": ""}
        }
        with open(result_path, "w", encoding="utf-8") as f:
            json.dump(result_content, f, ensure_ascii=False, indent=2)
        
        # 更新状态文件为SUCCESS
        status_file = Path(NOTE_OUTPUT_DIR) / f"{request.task_id}_status.json"
        if status_file.exists():
            with open(status_file, 'r', encoding='utf-8') as f:
                status_data = json.load(f)
            status_data["status"] = "SUCCESS"
            status_data["message"] = "手动替换完成"
            with open(status_file, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"笔记内容已手动替换: {request.task_id}")
        return R.success(data={
            "task_id": request.task_id,
            "markdown_length": len(request.markdown)
        })
    
    except Exception as e:
        logger.error(f"替换笔记失败: {e}")
        return R.fail(msg=f"替换笔记失败: {str(e)}")


@router.get("/manual_task")
async def get_manual_task():
    """
    获取最早的手动暂停任务（用户不知道 task_id，所以返回最早的一个）

    :return: 手动任务信息，包含提示词和字幕内容
    """
    try:
        output_dir = Path(NOTE_OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        manual_task_files = list(output_dir.glob("*.manual_task.json"))

        if not manual_task_files:
            return R.error(msg="没有等待手动导入的任务")

        manual_task_files.sort(key=lambda x: x.stat().st_mtime)

        latest_file = manual_task_files[0]
        with latest_file.open('r', encoding='utf-8') as f:
            task_data = json.load(f)

        return R.success(data={
            "task_id": task_data.get("task_id"),
            "status": task_data.get("status"),
            "title": task_data.get("title"),
            "video_url": task_data.get("video_url"),
            "platform": task_data.get("platform"),
            "transcript": task_data.get("transcript"),
            "prompt": task_data.get("prompt"),
            "options": task_data.get("options"),
        })

    except Exception as e:
        logger.error(f"获取手动任务失败: {e}")
        return R.error(msg=f"获取手动任务失败: {str(e)}")


class ManualTaskContinueRequest(BaseModel):
    """继续执行手动任务请求"""
    ai_generated_content: str


@router.post("/manual_task/{task_id}/continue")
async def continue_manual_task(task_id: str, request: ManualTaskContinueRequest):
    """
    导入大模型生成的内容，继续执行暂停的任务

    :param task_id: 任务ID
    :param ai_generated_content: 大模型生成的内容
    :return: 任务执行结果
    """
    try:
        result = NoteGenerator().continue_manual_task(task_id, request.ai_generated_content)

        if result is None:
            return R.error(msg="任务继续执行失败")

        return R.success(data={
            "task_id": task_id,
            "status": "SUCCESS",
            "markdown": result.markdown,
            "title": result.audio_meta.title,
        })

    except FileNotFoundError as e:
        return R.error(msg=str(e))
    except Exception as e:
        logger.error(f"继续执行手动任务失败: {e}")
        return R.error(msg=f"继续执行手动任务失败: {str(e)}")
