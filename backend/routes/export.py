"""Export routes — /api/export — export chats as MD, JSON, TXT"""

import json
from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from models.schemas import ExportFormat
from services import db_service

router = APIRouter()


def _escape_md_pipes(text: str) -> str:
    """Escape pipe characters outside fenced code blocks for safe Markdown export.

    Unescaped pipes in non-code content can accidentally create or break
    Markdown table syntax when the exported file is rendered.
        # Split text into lines for processing
    """
    lines = text.split("\n")
    h = False
    escaped: list[str] = []
        # Track code blocks to avoid escaping pipes inside fenced code
    for line in lines:
        stripped = line.lstrip()
                    # Toggle code block flag when encountering backticks
        if stripped.startswith("```"):
            in_code_block = not in_code_block
                            # Escape pipes in normal text to prevent Markdown table syntax issues
        if in_code_block:
            escaped.append(line)
        else:
            escaped.append(line.replace("|", r"\|"))
    return "\n".join(escaped)


class ExportMessagesRequest(BaseModel):
    message_ids: List[str]
    format: ExportFormat


@router.get("/{session_id}/{fmt}")
async def export_session(session_id: str, fmt: ExportFormat):
    session = db_service.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    messages = db_service.get_messages_full(session_id)
    title = session.get("title", "LocalMind Chat")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    if fmt == ExportFormat.json:
        content = json.dumps({"session": session, "messages": messages, "exported_at": ts}, indent=2, ensure_ascii=False)
        media = "application/json"
        filename = f"localmind_{session_id[:8]}.json"

    elif fmt == ExportFormat.markdown:
        lines = [f"# {title}\n", f"*Exported: {ts} | Model: {session.get('model','?')}*\n\n---\n"]
        for m in messages:
            role_label = "**You**" if m["role"] == "user" else "**LocalMind**"
            lines.append(f"{role_label}\n\n{_escape_md_pipes(m['content'])}\n")
            if m.get("sources"):
                lines.append(f"*Sources: {', '.join(m['sources'])}*\n")
            lines.append("\n---\n")
        content = "\n".join(lines)
        media = "text/markdown"
        filename = f"localmind_{session_id[:8]}.md"

    else:  # txt
        lines = [f"LocalMind Export — {title}", f"Exported: {ts}", "=" * 50, ""]
        for m in messages:
            role = "YOU" if m["role"] == "user" else "LOCALMIND"
            lines += [f"[{role}]", m["content"], ""]
        content = "\n".join(lines)
        media = "text/plain"
        filename = f"localmind_{session_id[:8]}.txt"

    return Response(
        content=content.encode("utf-8"),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/messages")
async def export_messages(req: ExportMessagesRequest):
    messages = db_service.get_messages_by_ids(req.message_ids)
    if not messages:
        raise HTTPException(404, "No messages found for the given IDs")

    messages.sort(key=lambda m: m.get("timestamp", ""))
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    if req.format == ExportFormat.json:
        content = json.dumps({"messages": messages, "exported_at": ts}, indent=2, ensure_ascii=False)
        media = "application/json"
        filename = f"localmind_messages_{ts.replace(' ', '_').replace(':', '-')}.json"

    elif req.format == ExportFormat.markdown:
        lines = ["# LocalMind – Exported Messages\n", f"*Exported: {ts}*\n\n---\n"]
        for m in messages:
            role_label = "**You**" if m["role"] == "user" else "**LocalMind**"
            lines.append(f"{role_label}\n\n{_escape_md_pipes(m['content'])}\n")
            if m.get("sources"):
                lines.append(f"*Sources: {', '.join(m['sources'])}*\n")
            lines.append("\n---\n")
        content = "\n".join(lines)
        media = "text/markdown"
        filename = f"localmind_messages_{ts.replace(' ', '_').replace(':', '-')}.md"

    else:
        lines = ["LocalMind Export — Selected Messages", f"Exported: {ts}", "=" * 50, ""]
        for m in messages:
            role = "YOU" if m["role"] == "user" else "LOCALMIND"
            lines += [f"[{role}]", m["content"], ""]
        content = "\n".join(lines)
        media = "text/plain"
        filename = f"localmind_messages_{ts.replace(' ', '_').replace(':', '-')}.txt"

    return Response(
        content=content.encode("utf-8"),
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
