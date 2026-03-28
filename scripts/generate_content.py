#!/usr/bin/env python3
"""
SNS Content Auto-Generator
Generates 2 weeks of content (14 posts) for:
  - チンアナゴ人生相談 (Garden Eel Life Advice)
  - POPPY GUMMY BEARS
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

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

HEADER = [
    "Date",
    "Series",
    "Topic or Scene",
    "EN Script",
    "JA Subtitle",
    "Image Prompt",       # POPPY only
    "Shooting Note",      # チンアナゴ only
    "EN Caption",
    "JA Caption",
    "Hashtags",
    "Status",
]

SERIES = ["チンアナゴ人生相談", "POPPY GUMMY BEARS"]

CHINANA_SYSTEM = """\
あなたはプロのSNSクリエイターです。
「チンアナゴ人生相談」シリーズ用のコンテンツを生成してください。

キャラクター設定:
- チンアナゴ（Garden Eel）が現代人の悩みに正論でキツめに答える
- 表情は基本的に無表情・真顔だが、ズバッと核心を突く

出力形式（JSONで返してください）:
{
  "topic": "相談テーマ（簡潔に）",
  "en_script": "英語セリフ（10秒以内、2〜3文）",
  "ja_subtitle": "日本語字幕（en_scriptの翻訳）",
  "shooting_note": "撮影メモ（実写向け：カメラアングル、照明、小道具など）",
  "en_caption": "Instagram/TikTok用英語キャプション（2〜3文）",
  "ja_caption": "日本語キャプション（2〜3文）",
  "hashtags": "ハッシュタグ（スペース区切り、10〜15個）"
}

ルール:
- en_script は自然な英語、話し言葉
- ja_subtitle は en_script に対応する字幕（直訳より自然な日本語）
- shooting_note は実写撮影の具体的な指示（チンアナゴのぬいぐるみ or フィギュアを使用）
- hashtags は英語と日本語を混在させてよい
"""

POPPY_SYSTEM = """\
あなたはプロのSNSクリエイターです。
「POPPY GUMMY BEARS」シリーズ用のコンテンツを生成してください。

キャラクター設定:
- Berry（赤いグミベア、元気・好奇心旺盛）
- Citron（黄色いグミベア・丸メガネ・インテリ風）
- Melron（緑のグミベア・ぽっちゃり・マイペース）
- 超リアル3Dレンダリング、ミニチュアスケール
- 人間サイズの日常空間に紛れ込む1シーン完結ストーリー

出力形式（JSONで返してください）:
{
  "scene": "シーン概要（簡潔に）",
  "en_script": "英語セリフ（10秒以内、キャラ名: セリフ の形式で）",
  "ja_subtitle": "日本語字幕（en_scriptの翻訳）",
  "image_prompt": "Freepik/Flux向け画像生成プロンプト（英語、詳細な描写）",
  "en_caption": "Instagram/TikTok用英語キャプション（2〜3文）",
  "ja_caption": "日本語キャプション（2〜3文）",
  "hashtags": "ハッシュタグ（スペース区切り、10〜15個）"
}

ルール:
- image_prompt は Freepik Flux に最適化、写実的3Dレンダリング指示を含む
  例: "ultra-realistic 3D render, miniature scale, photorealistic gummy bear characters..."
- セリフはキャラの個性を反映（Berry: 明るい、Citron: 論理的、Melron: のんびり）
- 毎回異なる日常シーン（キッチン、カフェ、公園、オフィスなど）を設定
- hashtags は英語と日本語を混在させてよい
"""


def get_sheets_client() -> gspread.Client:
    """Authenticate with Google Sheets API using service account credentials."""
    creds_json = os.environ["GOOGLE_CREDENTIALS_JSON"]
    creds_info = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    return gspread.authorize(creds)


def get_or_create_sheet(client: gspread.Client) -> gspread.Worksheet:
    """Get the worksheet, creating header row if it's empty."""
    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    try:
        sheet = spreadsheet.worksheet(SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=1000, cols=len(HEADER))

    # Add header if sheet is empty
    if sheet.row_count == 0 or not sheet.row_values(1):
        sheet.insert_row(HEADER, index=1)

    return sheet


def get_next_date(sheet: gspread.Worksheet) -> datetime.date:
    """Return the next date to use, based on the last date in the sheet."""
    all_values = sheet.get_all_values()

    # Skip header row; find last date entry
    for row in reversed(all_values[1:]):  # skip header
        if row and row[0]:
            try:
                last_date = datetime.date.fromisoformat(row[0])
                return last_date + datetime.timedelta(days=1)
            except ValueError:
                continue

    # Default: start from next Monday
    today = datetime.date.today()
    days_until_monday = (7 - today.weekday()) % 7 or 7
    return today + datetime.timedelta(days=days_until_monday)


def generate_chinana_content(client: anthropic.Anthropic, topic_hint: str = "") -> dict:
    """Generate one チンアナゴ人生相談 post via Claude."""
    user_prompt = (
        f"次のテーマでチンアナゴ人生相談のコンテンツを1件生成してください: {topic_hint}"
        if topic_hint
        else "現代人のあるある悩みを1つ選んでチンアナゴ人生相談のコンテンツを1件生成してください。"
        "仕事・SNS疲れ・人間関係など多様なテーマを扱ってください。"
    )

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        system=CHINANA_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text = message.content[0].text.strip()
    # Extract JSON (handle markdown code blocks)
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def generate_poppy_content(client: anthropic.Anthropic, scene_hint: str = "") -> dict:
    """Generate one POPPY GUMMY BEARS post via Claude."""
    user_prompt = (
        f"次のシーンでPOPPY GUMMY BEARSのコンテンツを1件生成してください: {scene_hint}"
        if scene_hint
        else "日常の面白いシーンを1つ選んでPOPPY GUMMY BEARSのコンテンツを1件生成してください。"
        "毎回異なるロケーション（キッチン、カフェ、電車内、公園など）を使ってください。"
    )

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        system=POPPY_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
    )

    text = message.content[0].text.strip()
    if "```" in text:
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def build_row(date: datetime.date, series: str, content: dict) -> list:
    """Convert a content dict into a spreadsheet row."""
    if series == "チンアナゴ人生相談":
        return [
            date.isoformat(),
            series,
            content.get("topic", ""),
            content.get("en_script", ""),
            content.get("ja_subtitle", ""),
            "",                                   # Image Prompt (N/A)
            content.get("shooting_note", ""),
            content.get("en_caption", ""),
            content.get("ja_caption", ""),
            content.get("hashtags", ""),
            "Draft",
        ]
    else:  # POPPY GUMMY BEARS
        return [
            date.isoformat(),
            series,
            content.get("scene", ""),
            content.get("en_script", ""),
            content.get("ja_subtitle", ""),
            content.get("image_prompt", ""),
            "",                                   # Shooting Note (N/A)
            content.get("en_caption", ""),
            content.get("ja_caption", ""),
            content.get("hashtags", ""),
            "Draft",
        ]


def main():
    print("🚀 Starting SNS content generation...")

    anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    sheets_client = get_sheets_client()
    sheet = get_or_create_sheet(sheets_client)

    start_date = get_next_date(sheet)
    print(f"📅 Generating content starting from: {start_date}")

    rows_to_append = []
    current_date = start_date

    # Generate 14 posts (2 weeks), alternating series
    for i in range(14):
        series = SERIES[i % 2]
        print(f"  [{i+1}/14] {current_date} — {series}")

        try:
            if series == "チンアナゴ人生相談":
                content = generate_chinana_content(anthropic_client)
            else:
                content = generate_poppy_content(anthropic_client)

            row = build_row(current_date, series, content)
            rows_to_append.append(row)

        except Exception as e:
            print(f"    ⚠️  Error generating content: {e}")
            # Append a placeholder row so dates stay consistent
            rows_to_append.append([
                current_date.isoformat(), series, "ERROR", str(e),
                "", "", "", "", "", "", "Error",
            ])

        current_date += datetime.timedelta(days=1)

    # Batch-append all rows
    sheet.append_rows(rows_to_append, value_input_option="USER_ENTERED")
    print(f"✅ Appended {len(rows_to_append)} rows to spreadsheet.")
    print(f"   Spreadsheet: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")


if __name__ == "__main__":
    main()
