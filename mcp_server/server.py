import json
import aiosqlite
from mcp.server.fastmcp import FastMCP

DB_PATH = "/Users/nantang/Library/Application Support/com.meetily.ai/meeting_minutes.sqlite"

mcp = FastMCP("meetily")


@mcp.tool()
async def list_meetings(limit: int = 20) -> str:
    """List recent meetings with their id, title, and creation date."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, title, created_at FROM meetings ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        return "No meetings found."

    meetings = [{"id": r[0], "title": r[1], "created_at": r[2]} for r in rows]
    return json.dumps(meetings, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_meeting_summary(meeting_id: str) -> str:
    """Get the structured summary for a meeting by its ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Get meeting title
        async with db.execute(
            "SELECT title, created_at FROM meetings WHERE id = ?", (meeting_id,)
        ) as cursor:
            meeting = await cursor.fetchone()

        if not meeting:
            return f"Meeting {meeting_id} not found."

        # Get summary result
        async with db.execute(
            "SELECT result, status FROM summary_processes WHERE meeting_id = ?",
            (meeting_id,),
        ) as cursor:
            row = await cursor.fetchone()

    if not row or not row[0]:
        # Fallback: return raw transcript so Claude can summarize directly
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT transcript FROM transcripts WHERE meeting_id = ? ORDER BY timestamp",
                (meeting_id,),
            ) as cursor:
                t_rows = await cursor.fetchall()

        if not t_rows:
            return f"No summary or transcript found for meeting '{meeting[0]}'."

        full_text = " ".join(r[0] for r in t_rows if r[0] and r[0].strip())
        text = full_text[:30000]
        truncated = " (truncated)" if len(full_text) > 30000 else ""
        return (
            f"# {meeting[0]}\nDate: {meeting[1]}\n"
            f"(No pre-generated summary available{truncated} — raw transcript below. Please summarize.)\n\n"
            + text
        )

    try:
        result = json.loads(row[0])
    except json.JSONDecodeError:
        return f"Summary data is malformed for meeting '{meeting[0]}'."

    sections = ["People", "SessionSummary", "KeyItemsDecisions",
                "ImmediateActionItems", "NextSteps", "CriticalDeadlines"]

    output = [f"# {meeting[0]}", f"Date: {meeting[1]}", ""]

    for section in sections:
        if section not in result:
            continue
        output.append(f"## {section}")
        content = result[section]
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    text = block.get("content") or block.get("text") or str(block)
                else:
                    text = str(block)
                output.append(f"- {text}")
        else:
            output.append(str(content))
        output.append("")

    return "\n".join(output)


@mcp.tool()
async def search_meetings(query: str) -> str:
    """Search across meeting transcripts and summaries for a keyword or phrase."""
    pattern = f"%{query}%"

    async with aiosqlite.connect(DB_PATH) as db:
        # Search in transcripts
        async with db.execute(
            """
            SELECT m.id, m.title, m.created_at, t.transcript
            FROM transcripts t
            JOIN meetings m ON t.meeting_id = m.id
            WHERE t.transcript LIKE ?
            ORDER BY m.created_at DESC
            LIMIT 10
            """,
            (pattern,),
        ) as cursor:
            transcript_hits = await cursor.fetchall()

        # Search in summary results
        async with db.execute(
            """
            SELECT m.id, m.title, m.created_at, sp.result
            FROM summary_processes sp
            JOIN meetings m ON sp.meeting_id = m.id
            WHERE sp.result LIKE ?
            ORDER BY m.created_at DESC
            LIMIT 10
            """,
            (pattern,),
        ) as cursor:
            summary_hits = await cursor.fetchall()

    if not transcript_hits and not summary_hits:
        return f"No meetings found matching '{query}'."

    seen = set()
    results = []

    for row in transcript_hits:
        mid, title, created_at, transcript = row
        if mid in seen:
            continue
        seen.add(mid)
        # Extract a short snippet around the match
        idx = transcript.lower().find(query.lower())
        snippet = transcript[max(0, idx - 80): idx + 120].strip()
        results.append({
            "meeting_id": mid,
            "title": title,
            "date": created_at,
            "source": "transcript",
            "snippet": f"...{snippet}...",
        })

    for row in summary_hits:
        mid, title, created_at, result_json = row
        if mid in seen:
            continue
        seen.add(mid)
        # Find matching content in summary blocks
        snippet = ""
        try:
            result = json.loads(result_json)
            for section_content in result.values():
                if isinstance(section_content, list):
                    for block in section_content:
                        text = ""
                        if isinstance(block, dict):
                            text = block.get("content") or block.get("text") or ""
                        if query.lower() in text.lower():
                            snippet = text[:200]
                            break
                if snippet:
                    break
        except (json.JSONDecodeError, AttributeError):
            pass
        results.append({
            "meeting_id": mid,
            "title": title,
            "date": created_at,
            "source": "summary",
            "snippet": snippet or "(match found in summary)",
        })

    return json.dumps(results, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_action_items(person: str = "") -> str:
    """
    Get all action items and next steps across meetings.
    If person is provided, filter to items mentioning that person.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            """
            SELECT m.title, m.created_at, sp.result
            FROM summary_processes sp
            JOIN meetings m ON sp.meeting_id = m.id
            WHERE sp.result IS NOT NULL
            ORDER BY m.created_at DESC
            """,
        ) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        return "No processed meetings found."

    action_sections = ["ImmediateActionItems", "NextSteps"]
    items = []

    for title, created_at, result_json in rows:
        try:
            result = json.loads(result_json)
        except (json.JSONDecodeError, TypeError):
            continue

        for section in action_sections:
            if section not in result:
                continue
            blocks = result[section]
            if not isinstance(blocks, list):
                continue
            for block in blocks:
                text = ""
                if isinstance(block, dict):
                    text = block.get("content") or block.get("text") or ""
                else:
                    text = str(block)

                if person and person.lower() not in text.lower():
                    continue

                items.append({
                    "meeting_title": title,
                    "date": created_at,
                    "section": section,
                    "task": text,
                })

    if not items:
        msg = f"No action items found for '{person}'." if person else "No action items found."
        return msg

    return json.dumps(items, ensure_ascii=False, indent=2)


@mcp.tool()
async def get_meeting_transcript(meeting_id: str, max_chars: int = 30000) -> str:
    """
    Get the raw transcript text for a meeting by its ID.
    Use this when no summary is available (e.g. summary generation failed).
    Claude can then summarize the transcript directly.
    max_chars limits the returned text to avoid context overflow (default 30000).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT title, created_at FROM meetings WHERE id = ?", (meeting_id,)
        ) as cursor:
            meeting = await cursor.fetchone()

        if not meeting:
            return f"Meeting {meeting_id} not found."

        async with db.execute(
            """
            SELECT transcript FROM transcripts
            WHERE meeting_id = ?
            ORDER BY timestamp
            """,
            (meeting_id,),
        ) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        return f"No transcript found for meeting '{meeting[0]}'."

    full_text = " ".join(r[0] for r in rows if r[0] and r[0].strip())

    truncated = len(full_text) > max_chars
    text = full_text[:max_chars]

    header = f"# Transcript: {meeting[0]}\nDate: {meeting[1]}\n"
    if truncated:
        header += f"(Showing first {max_chars} of {len(full_text)} characters)\n"
    header += "\n"

    return header + text


if __name__ == "__main__":
    mcp.run()
