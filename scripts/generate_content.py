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

## キャラクター
チンアナゴ（Garden Eel）は砂の中からにょろっと顔を出す、見た目はかわいいが口が辛口な海の住人。
かわいい声でさらっと核心を突く。怒らず、淡々と、でもズバッと。

## コンテンツ構成
現代人の「あるある状況」を1文で描写し、チンアナゴが正論をひと言で返す。
2文合わせて1本の完成セリフ。

良い例：
- 「休日なのに仕事のことを考えてしまう。オンとオフの境界線、引けてないだけ。」
- 「いいね数が少ないとテンションが下がる。承認、外に求めすぎ。」
- 「ダイエット、また明日からにした。明日から、ずっと言ってる。」
- 「嫌いな上司にも笑顔で対応してしまう。顔と気持ち、別人だもんね。」
- 「推しのグッズを買いすぎて部屋が埋まってきた。愛情表現、物量で測るタイプ。」

## テーマカテゴリー（毎回バラバラに選ぶこと）
以下のカテゴリーから偏らず幅広く選んでください。

【仕事・職場】
会議が長い／指示が毎回変わる上司／残業が当たり前／評価されない／締め切り先送り／
リモートで集中できない／メールが返せず溜まる／同僚との微妙な空気／有休が取れない雰囲気／
昇進したくないのに期待される

【SNS・スマホ依存】
いいね数が気になる／ストーリーの閲覧者を確認する／寝る前にSNSがやめられない／
映えのために料理が冷める／フォロワー数で人を判断してしまう／
TikTokを見始めると止まらない／炎上が怖くて本音が言えない／
リア充投稿を見て落ち込む

【人間関係・コミュニケーション】
飲み会を断れない／本音が言えない／グループLINEの既読が気になる／
自分だけ誘われていないと気づく／友達の自慢話を聞き続ける／
嫌いな人にも愛想よくしてしまう／話を聞いているふりが上手くなってきた／
気を使いすぎて疲れる

【恋愛・マッチング】
告白できないまま時間が経つ／元カレ元カノのSNSを見てしまう／
マッチングアプリで消耗する／返信が遅いと浮気を疑う／
好きな人の前でキャラが変わる／記念日を忘れられた／
相手に求めすぎてしまう

【お金・消費】
給料日前に残高がやばい／セールで不要なものを買う／サブスクを解約できない／
推しへの課金が止まらない／老後の不安だけ育っている／
コンビニで予算オーバーする／ポイントを貯めるために余計に買う

【健康・生活習慣】
ダイエットが三日坊主／深夜に食べてしまう／運動しようと思いながら寝る／
朝起きられない／目が疲れているのにスマホをやめない／
姿勢が悪いとわかっているが直らない／水を飲まない

【自己成長・メンタル】
他人と比べてしまう／承認欲求が強い／夢はあるが動けない／
完璧主義で何も完成しない／「いつかやる」がずっとそのまま／
やる気が出るまで待ってしまう／自己肯定感が低い割に自意識は高い／
褒められると逆に不安になる

【現代あるある・その他】
AI に仕事を奪われる不安／サステナブルと言いながら通販しまくる／
推し活が唯一の生きがい／ふるさと納税を毎年忘れる／
健康診断の結果を見ない／年齢を言い訳にし始めた／
親の老いに気づいた日

## 出力ルール
- 必ず指定された件数をJSON配列で返す
- 各要素は {"script": "..."} の形式のみ
- script: あるある状況（1文）＋チンアナゴの一言（1文）を句点でつなげた1つのセリフ（計30〜50文字程度）
- 14件の場合、上記カテゴリーから最低7カテゴリー以上にまたがること
- 全件で内容が被らないようにする
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


def get_existing_scripts(sheet: gspread.Worksheet) -> list[str]:
    all_values = sheet.get_all_values()
    scripts = []
    for row in all_values[1:]:
        if len(row) > 4 and row[4]:
            scripts.append(row[4])
    return scripts


def generate_content(client: anthropic.Anthropic, existing_scripts: list[str]) -> list[dict]:
    avoid_text = ""
    if existing_scripts:
        recent = existing_scripts[-20:]
        avoid_text = (
            "\n\n以下は既出なので同じ内容・テーマは使わないでください:\n"
            + "\n".join(f"- {t}" for t in recent)
        )

    user_prompt = (
        f"{NUM_POSTS}件のチンアナゴ人生相談セリフを生成してください。"
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
    existing_scripts = get_existing_scripts(sheet)
    print(f"Generating {NUM_POSTS} posts from {start_date}")

    items = generate_content(anthropic_client, existing_scripts)

    rows = []
    for i, item in enumerate(items):
        date = start_date + datetime.timedelta(days=i)
        script = item.get("script", "")
        rows.append([
            date.isoformat(),    # A: Date
            "チンアナゴ人生相談", # B: Series
            "",                  # C: Topic or Scene
            "",                  # D: EN Script
            script,              # E: JA Subtitle（完成セリフ）
            "",                  # F: Image Prompt
            "",                  # G: Shooting Note
            "",                  # H: EN Caption
            "",                  # I: JA Caption
            "",                  # J: Hashtags
            "Draft",             # K: Status
        ])
        print(f"  [{i+1}/{NUM_POSTS}] {date} | {script}")

    sheet.append_rows(rows, value_input_option="USER_ENTERED")
    print(f"Done. Appended {len(rows)} rows.")


if __name__ == "__main__":
    main()
