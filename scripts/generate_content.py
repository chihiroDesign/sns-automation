#!/usr/bin/env python3
"""
SNS Content Auto-Generator
Generates 2 weeks (14 posts) of チンアナゴ人生相談 content
and appends them to a Google Spreadsheet.
"""

import os
import json
import datetime
import anthropic
import gspread
from google.oauth2.service_account import Credentials

# ── Constants ──────────────────────────────────────────────────────────────────

SPREADSHEET_ID = os.environ["SPREADSHEET_ID"]
SHEET_NAME = "Content"
NUM_POSTS = 14

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

HEADER = [
    "Date",
    "Series",
    "Topic or Scene",
    "EN Script",
    "JA Subtitle",
    "Image Prompt",
    "Shooting Note",
    "EN Caption",
    "JA Caption",
    "Hashtags",
    "Status",
]

SYSTEM_PROMPT = """\
あなたは「チンアナゴ人生相談」のSNSコンテンツライターです。

コンセプト:
- 現代人のあるある悩み（仕事・SNS疲れ・人間関係・恋愛・生活習慣など）に対し、
  チンアナゴが正論でキツめに一言で返す。
- 無表情で淡々と核心を突くスタイル。

出力ルール:
- 必ず指定された件数をJSON配列で返す
- 各要素は {"topic": "...", "ja_subtitle": "..."} の形式
- topic: 相談テーマ（現代人のあるある、10〜20文字程度）
- ja_subtitle: チンアナゴの一言（正論でキツめ、15〜30文字程度、句読点含む）
- 全件で topic が被らないようにする
- JSONのみ出力。前後に説明文を入れない
"""


def get_sheets_client() -> gspread.Client:
    creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
    creds_info = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return gspread.authorize(creds)


def get_or_create_sheet(client: gspread.Client) -> gspread.Worksheet:
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    try:
        sheet = spreadsheet.worksheet(SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=len(HEADER))

    if sheet.row_count == 0 or not sheet.row_values(1):
        sheet.insert_row(HEADER, index=1)
    return sheet


def get_next_date(sheet: gspread.Worksheet) -> datetime.date:
    all_values = sheet.get_all_values()
    for row in reversed(all_values[1:]):
        if row and row[0]:
            try:
                return datetime.date.fromisoformat(row[0]) + datetime.timedelta(days=1)
            except ValueError:
                continue
    today = datetime.date.today()
    days_until_monday = (7 - today.weekday()) % 7 or 7
    return today + datetime.timedelta(days=days_until_monday)


def get_existing_topics(sheet: gspread.Worksheet) -> list[str]:
    all_values = sheet.get_all_values()
    topics = []
    for row in all_values[1:]:
        if len(row) > 2 and row[2]:
            topics.append(row[2])
    return topics


def generate_content(client: anthropic.Anthropic, existing_topics: list[str]) -> list[dict]:
    avoid_text = ""
    if existing_topics:
        recent = existing_topics[-20:]
        avoid_text = (
            "\n\n以下のトピックは既出なので絶対に使わないでください:\n"
            + "\n".join(f"- {t}" for t in recent)
        )

    user_prompt = (
        f"{NUM_POSTS}件のチンアナゴ人生相談コンテンツを生成してください。"
        f"{avoid_text}"
    )

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text = message.content[0].text.strip()
    # Extract JSON array
    if "```" in text:
        for part in text.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("["):
                text = part
                break
    start = text.find("[")
    end = text.rfind("]") + 1
    if start != -1 and end > start:
        text = text[start:end]

    items = json.loads(text)
    if len(items) != NUM_POSTS:
        print(f"  ⚠️  Expected {NUM_POSTS} items, got {len(items)}")
    return items[:NUM_POSTS]


def main():
    print("Starting content generation...")

    anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    sheets_client = get_sheets_client()
    sheet = get_or_create_sheet(sheets_client)

    start_date = get_next_date(sheet)
    existing_topics = get_existing_topics(sheet)
    print(f"Generating {NUM_POSTS} posts from {start_date}")

    items = generate_content(anthropic_client, existing_topics)

    rows = []
    for i, item in enumerate(items):
        date = start_date + datetime.timedelta(days=i)
        rows.append([
            date.isoformat(),          # A: Date
            "チンアナゴ人生相談",       # B: Series
            item.get("topic", ""),     # C: Topic or Scene
            "",                        # D: EN Script
            item.get("ja_subtitle", ""),  # E: JA Subtitle
            "",                        # F: Image Prompt
            "",                        # G: Shooting Note
            "",                        # H: EN Caption
            "",                        # I: JA Caption
            "",                        # J: Hashtags
            "Draft",                   # K: Status
        ])
        print(f"  [{i+1}/{NUM_POSTS}] {date} | {item.get('topic', '')} → {item.get('ja_subtitle', '')}")

    sheet.append_rows(rows, value_input_option="USER_ENTERED")
    print(f"Done. Appended {len(rows)} rows.")


if __name__ == "__main__":
    main()
