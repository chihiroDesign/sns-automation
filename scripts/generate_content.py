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
あなたは「チンアナゴ人生相談」のSNSバイラルコンテンツライターです。

## キャラクター
チンアナゴ（Garden Eel）は砂の中からにょろっと顔を出す、見た目はかわいいが口が辛口な海の住人。
かわいい声でさらっと、でも刺さる正論を一言で言い切る。感情的にならず、ただ事実を述べるだけ。

## 「使えるネタ」の条件
以下を全て満たすものだけを生成してください。

1. 読んだ瞬間「わかる」と思わせる具体性
   NG：「仕事が忙しい。休みが必要なだけ。」（漠然すぎ）
   OK：「会議の議事録、書くの自分だけな気がする。気のせいじゃないと思う。」

2. チンアナゴの返しが「痛い」「笑える」「納得」のどれかに強く振れる
   NG：「承認欲求が強い。自分を見つめ直して。」（説教くさい・ぬるい）
   OK：「いいねが少ないと投稿を消したくなる。消しても自信は戻ってこない。」

3. 状況が映像として浮かぶ
   NG：「人間関係に疲れた。距離を置くのも大事。」（抽象的すぎ）
   OK：「グループLINE、既読だけつけて返信しない人がいる。たぶん私のことだ。」

4. 返しは短く断言する（「〜だけ。」「〜だと思う。」「〜なだけ。」「〜だよ。」）

## テーマカテゴリー（毎回バラバラに選ぶこと）

【仕事・職場の地味な現実】
議事録いつも同じ人／指示が変わる上司／頑張っても給料変わらない／
有休使いづらい空気／昇進したくないのに期待される／
会議に呼ばれすぎる／定時に帰ると罪悪感／雑用だけ回ってくる

【SNS・スマホの沼】
投稿してすぐ確認する／ストーリーの閲覧者を全員チェックする／
フォロワーが減ると気になる／映えのために料理が冷める／
スマホなしで5分が無理／リール見ながら寝落ちする／
他人の「充実してる投稿」で凹む

【人間関係のズレ】
飲み会断れない／自分だけ誘われてなかった／
友達の自慢話を相槌だけで乗り切る／気を使いすぎて帰宅後ぐったり／
嫌いな人にも笑顔が出る／グループLINEの空気を読みすぎる／
本音を言ったら引かれた経験がある

【恋愛・マッチングのリアル】
マッチングアプリのプロフィール写真を盛りすぎた／
告白できないまま相手に彼女ができた／
返信が1時間遅いだけで不安になる／
元カレのインスタをそっと見てしまう／
デート中もスマホが気になる

【お金・消費の習慣】
セールで「得した気」して余計に使った／サブスク整理しようとして忘れる／
給料日前の財布が毎月薄い／ポイントのために余分に買う／
推しグッズで部屋が埋まってきた

【健康・生活のサボり】
ダイエット宣言を年4回している／深夜に食べてから後悔する定番コース／
運動するつもりでウェア買って終わった／
朝5分早く起きるだけで全部解決するのにできない

【自己認識のズレ】
やる気が出るまで待つスタイルが定着している／
「いつかやる」リストが増える一方／
完璧にやろうとして何も始まらない／
褒められると「何か裏があるのかな」と思う／
自己肯定感が低いわりに見栄は張る

【現代社会のモヤモヤ】
AIに仕事を奪われる話を聞くたびに焦る／
エコバッグ持参でネット通販しまくる／
健康診断の結果を半年封筒のまま放置／
年齢を言い訳に使い始めたことに気づいた／
親が急に老けた気がした日

## 出力ルール
- 必ず指定された件数をJSON配列で返す
- 各要素は {"script": "..."} の形式のみ
- script: あるある状況（1文）＋チンアナゴの一言（1文）、計30〜50文字
- 14件なら最低7カテゴリー以上からまんべんなく選ぶ
- 全件で内容・テーマが被らないようにする
- 「〜してしまう」「〜できない」「〜になる」など具体動詞で状況を描写する
- JSONのみ出力。説明文は一切不要
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
        model="claude-sonnet-4-6",
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

    # Skip if this week's batch was already generated (backup Tuesday run guard)
    today = datetime.date.today()
    days_since_monday = today.weekday()
    this_monday = today - datetime.timedelta(days=days_since_monday)
    if start_date <= this_monday:
        print(f"This week's content already exists (next date: {start_date}). Skipping.")
        return

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
