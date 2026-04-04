'use strict';

/**
 * Chinnanago Life Advice Auto-Posting Pipeline
 *
 * Reads one unprocessed "チンアナゴ人生相談" row from Google Sheets (Content sheet),
 * generates a serif via Claude, creates an audio video via Freepik Kling 3.0 Omni,
 * generates a caption/hashtags via Claude, then posts to Instagram Reels and TikTok.
 */

const { google } = require('googleapis');
const Anthropic = require('@anthropic-ai/sdk');
const axios = require('axios');
const fs = require('fs');

// ── Environment Variables ──────────────────────────────────────────────────────
const SPREADSHEET_ID = process.env.SPREADSHEET_ID;
const GOOGLE_CREDENTIALS_JSON = process.env.GOOGLE_CREDENTIALS_JSON;
const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY;
const FREEPIK_API_KEY = process.env.FREEPIK_API_KEY;
const CHINNANAGO_IMAGE_URL = process.env.CHINNANAGO_IMAGE_URL;
const INSTAGRAM_ACCESS_TOKEN = process.env.INSTAGRAM_ACCESS_TOKEN;
const TIKTOK_ACCESS_TOKEN = process.env.TIKTOK_ACCESS_TOKEN;

const SHEET_NAME = 'Content';
const TMP_VIDEO_PATH = '/tmp/chinnanago_temp.mp4';

// Column indices (0-based): A=0, B=1, C=2, ...
const COL = {
  DATE: 0,          // A
  SERIES: 1,        // B
  TOPIC: 2,         // C
  EN_SCRIPT: 3,     // D
  JA_SUBTITLE: 4,   // E
  IMAGE_PROMPT: 5,  // F - video URL is stored here
  SHOOTING_NOTE: 6, // G
  EN_CAPTION: 7,    // H
  JA_CAPTION: 8,    // I
  HASHTAGS: 9,      // J
  STATUS: 10,       // K
};

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ── Google Sheets ──────────────────────────────────────────────────────────────

async function getSheetsClient() {
  const credentials = JSON.parse(GOOGLE_CREDENTIALS_JSON);
  const auth = new google.auth.GoogleAuth({
    credentials,
    scopes: ['https://www.googleapis.com/auth/spreadsheets'],
  });
  return google.sheets({ version: 'v4', auth });
}

/**
 * Finds the first row where B="チンアナゴ人生相談" and K is empty.
 * Returns { rowNumber (1-based), data (array) } or null if none found.
 */
async function getTargetRow(sheets) {
  const res = await sheets.spreadsheets.values.get({
    spreadsheetId: SPREADSHEET_ID,
    range: `${SHEET_NAME}!A:K`,
  });
  const rows = res.data.values || [];
  // Index 0 is header row; skip it
  for (let i = 1; i < rows.length; i++) {
    const row = rows[i];
    const series = (row[COL.SERIES] || '').trim();
    const status = (row[COL.STATUS] || '').trim();
    if (series === 'チンアナゴ人生相談' && status === '') {
      return { rowNumber: i + 1, data: row };
    }
  }
  return null;
}

async function updateCell(sheets, rowNumber, colIndex, value) {
  const colLetter = String.fromCharCode(65 + colIndex);
  const range = `${SHEET_NAME}!${colLetter}${rowNumber}`;
  await sheets.spreadsheets.values.update({
    spreadsheetId: SPREADSHEET_ID,
    range,
    valueInputOption: 'RAW',
    requestBody: { values: [[value]] },
  });
}

// ── Claude API ─────────────────────────────────────────────────────────────────

async function generateSerif(topic) {
  const client = new Anthropic({ apiKey: ANTHROPIC_API_KEY });
  const response = await client.messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 256,
    system: `あなたはチンアナゴです。水槽の砂の中から顔を出したり引っ込めたりしながら、人生相談に答えます。
- 語尾は「にょ」や「にょろ」を時々使う
- 相談に対してズレた角度から的を射た答えを返す
- シュールで愛嬌があり、少し哲学的
- 50〜80文字程度
- 日本語のみ
- セリフのテキストのみ返してください。説明や前置きは不要です。`,
    messages: [{ role: 'user', content: `お悩み：${topic}` }],
  });
  return response.content[0].text.trim();
}

async function generateCaption(topic, serif) {
  const client = new Anthropic({ apiKey: ANTHROPIC_API_KEY });
  const response = await client.messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 512,
    messages: [{
      role: 'user',
      content: `以下のチンアナゴのセリフをもとに、InstagramとTikTok用の投稿キャプションとハッシュタグを作成してください。

お悩み：${topic}
セリフ：${serif}

条件：
- 冒頭にお悩みを1行で引用（例：「毎日仕事がつらい…というお悩みに」）
- チンアナゴのセリフを引用
- 共感を呼ぶ一言を追加
- ハッシュタグ：#チンアナゴ #人生相談 #AI #癒し #水槽 + 内容に合うもの3〜5個
- キャプション本文は100文字以内
- 以下のJSON形式のみ返してください（余計な文字は不要）：
{"caption": "...", "hashtags": "#チンアナゴ #人生相談 ..."}`,
    }],
  });
  let text = response.content[0].text.trim();
  // Strip markdown code fences if present
  text = text.replace(/^```json\s*/m, '').replace(/\s*```$/m, '').trim();
  const start = text.indexOf('{');
  const end = text.lastIndexOf('}') + 1;
  if (start === -1 || end === 0) throw new Error(`Invalid JSON from Claude: ${text}`);
  return JSON.parse(text.slice(start, end));
}

// ── Freepik Kling 3.0 Omni ────────────────────────────────────────────────────

async function generateVideo(serif) {
  const prompt =
    `・チンアナゴが人生についてエールを送るシュールな動画。\n` +
    `・セリフ：\n　${serif}\n` +
    `・幼女のようなかわいい声`;

  const endpoint = 'https://api.freepik.com/v1/ai/image-to-video/kling-v2';
  const requestBody = {
    duration: '10',
    image: CHINNANAGO_IMAGE_URL,
    prompt,
    negative_prompt: 'blur, distort, low quality',
    cfg_scale: 0.5,
  };
  const requestHeaders = {
    'Content-Type': 'application/json',
    'x-freepik-api-key': FREEPIK_API_KEY,
  };

  console.log('[Freepik] Submitting video task...');
  console.log('[Freepik] Endpoint:', endpoint);
  console.log('[Freepik] Headers:', JSON.stringify({
    ...requestHeaders,
    'x-freepik-api-key': FREEPIK_API_KEY ? `***${FREEPIK_API_KEY.slice(-4)}` : '(not set)',
  }));
  console.log('[Freepik] Request body:', JSON.stringify(requestBody, null, 2));

  let submitRes;
  try {
    submitRes = await axios.post(endpoint, requestBody, { headers: requestHeaders });
  } catch (err) {
    const status = err.response?.status;
    const data = err.response?.data;
    console.error(`[Freepik] HTTP ${status} error`);
    console.error('[Freepik] Response headers:', JSON.stringify(err.response?.headers));
    console.error('[Freepik] Response body:', JSON.stringify(data));
    throw new Error(`Freepik API ${status}: ${JSON.stringify(data)}`);
  }

  console.log('[Freepik] Submit response status:', submitRes.status);
  console.log('[Freepik] Submit response body:', JSON.stringify(submitRes.data));

  const taskId = submitRes.data?.data?.task_id ?? submitRes.data?.task_id;
  if (!taskId) {
    throw new Error(`No task_id in Freepik response: ${JSON.stringify(submitRes.data)}`);
  }
  console.log(`[Freepik] Task ID: ${taskId}`);

  // Poll every 10 seconds, up to 90 attempts (15 minutes max)
  for (let attempt = 1; attempt <= 90; attempt++) {
    await sleep(10000);
    const pollRes = await axios.get(
      `https://api.freepik.com/v1/ai/image-to-video/kling-v2/${taskId}`,
      { headers: { 'x-freepik-api-key': FREEPIK_API_KEY } }
    );

    const status = pollRes.data?.data?.status ?? pollRes.data?.status;
    console.log(`[Freepik] Attempt ${attempt}/90, status: ${status}`);

    if (status === 'COMPLETED') {
      const videoUrl = pollRes.data?.data?.video_url ?? pollRes.data?.video_url;
      if (!videoUrl) {
        throw new Error('No video_url in completed Freepik response');
      }
      return videoUrl;
    }

    if (status === 'FAILED') {
      throw new Error(`Freepik task FAILED: ${JSON.stringify(pollRes.data)}`);
    }
  }

  throw new Error('error: timeout');
}

// ── Video Download ─────────────────────────────────────────────────────────────

async function downloadVideo(videoUrl) {
  console.log(`[Download] Downloading from ${videoUrl}`);
  const response = await axios.get(videoUrl, { responseType: 'arraybuffer' });
  fs.writeFileSync(TMP_VIDEO_PATH, Buffer.from(response.data));
  console.log(`[Download] Saved to ${TMP_VIDEO_PATH}`);
}

// ── Instagram Reels ────────────────────────────────────────────────────────────

async function postToInstagram(videoUrl, caption, hashtags) {
  const postText = `${caption}\n\n${hashtags}`;

  // Retrieve Instagram Business Account ID linked to the token
  const profileRes = await axios.get('https://graph.facebook.com/v18.0/me', {
    params: {
      fields: 'id,instagram_business_account',
      access_token: INSTAGRAM_ACCESS_TOKEN,
    },
  });
  const igAccountId = profileRes.data?.instagram_business_account?.id;
  if (!igAccountId) {
    throw new Error('Instagram Business Account ID not found in token profile');
  }
  console.log(`[Instagram] Account ID: ${igAccountId}`);

  // Step 1: Create Reels media container
  const containerRes = await axios.post(
    `https://graph.facebook.com/v18.0/${igAccountId}/media`,
    null,
    {
      params: {
        media_type: 'REELS',
        video_url: videoUrl,
        caption: postText,
        access_token: INSTAGRAM_ACCESS_TOKEN,
      },
    }
  );
  const containerId = containerRes.data?.id;
  if (!containerId) {
    throw new Error(`Failed to create IG media container: ${JSON.stringify(containerRes.data)}`);
  }
  console.log(`[Instagram] Container ID: ${containerId}`);

  // Step 2: Poll container until FINISHED
  for (let attempt = 1; attempt <= 30; attempt++) {
    await sleep(10000);
    const statusRes = await axios.get(
      `https://graph.facebook.com/v18.0/${containerId}`,
      {
        params: {
          fields: 'status_code',
          access_token: INSTAGRAM_ACCESS_TOKEN,
        },
      }
    );
    const statusCode = statusRes.data?.status_code;
    console.log(`[Instagram] Container status (${attempt}/30): ${statusCode}`);
    if (statusCode === 'FINISHED') break;
    if (statusCode === 'ERROR') {
      throw new Error('Instagram media container processing failed');
    }
    if (attempt === 30) {
      throw new Error('Instagram media container timed out after 30 attempts');
    }
  }

  // Step 3: Publish
  const publishRes = await axios.post(
    `https://graph.facebook.com/v18.0/${igAccountId}/media_publish`,
    null,
    {
      params: {
        creation_id: containerId,
        access_token: INSTAGRAM_ACCESS_TOKEN,
      },
    }
  );
  console.log(`[Instagram] Published! Post ID: ${publishRes.data?.id}`);
}

// ── TikTok ─────────────────────────────────────────────────────────────────────

async function postToTikTok(caption, hashtags) {
  const title = `${caption}\n\n${hashtags}`;
  const videoData = fs.readFileSync(TMP_VIDEO_PATH);
  const fileSize = videoData.length;

  // Step 1: Initialize upload session
  const initRes = await axios.post(
    'https://open.tiktokapis.com/v2/post/publish/video/init/',
    {
      post_info: {
        title,
        privacy_level: 'PUBLIC_TO_EVERYONE',
        disable_duet: false,
        disable_comment: false,
        disable_stitch: false,
      },
      source_info: {
        source: 'FILE_UPLOAD',
        video_size: fileSize,
        chunk_size: fileSize,
        total_chunk_count: 1,
      },
    },
    {
      headers: {
        Authorization: `Bearer ${TIKTOK_ACCESS_TOKEN}`,
        'Content-Type': 'application/json; charset=UTF-8',
      },
    }
  );

  const publishId = initRes.data?.data?.publish_id;
  const uploadUrl = initRes.data?.data?.upload_url;
  if (!publishId || !uploadUrl) {
    throw new Error(`TikTok init upload failed: ${JSON.stringify(initRes.data)}`);
  }
  console.log(`[TikTok] publish_id: ${publishId}`);

  // Step 2: Upload video in one chunk
  await axios.put(uploadUrl, videoData, {
    headers: {
      'Content-Type': 'video/mp4',
      'Content-Range': `bytes 0-${fileSize - 1}/${fileSize}`,
      'Content-Length': String(fileSize),
    },
    maxContentLength: Infinity,
    maxBodyLength: Infinity,
  });
  console.log('[TikTok] Video uploaded successfully');
}

// ── Main ───────────────────────────────────────────────────────────────────────

async function main() {
  console.log('=== Chinnanago Pipeline Start ===');

  const sheets = await getSheetsClient();

  // Step 1: Get unprocessed row
  console.log('[Step 1] Fetching target row...');
  const target = await getTargetRow(sheets);
  if (!target) {
    console.log('No unprocessed チンアナゴ人生相談 rows found. Exiting normally.');
    return;
  }

  const { rowNumber, data } = target;
  const topic = (data[COL.TOPIC] || '').trim();
  console.log(`[Step 1] Row ${rowNumber}: topic="${topic}"`);

  // Mark as processing immediately to prevent double-execution
  await updateCell(sheets, rowNumber, COL.STATUS, 'processing');

  let serif, videoUrl, captionData;

  // Step 2: Generate serif (Claude)
  try {
    console.log('[Step 2] Generating serif via Claude...');
    serif = await generateSerif(topic);
    console.log(`[Step 2] Serif: ${serif}`);
    await updateCell(sheets, rowNumber, COL.JA_SUBTITLE, serif);
  } catch (err) {
    console.error('[Step 2] Error:', err.message);
    await updateCell(sheets, rowNumber, COL.STATUS, 'error');
    return;
  }

  // Step 3: Generate video (Freepik Kling)
  try {
    console.log('[Step 3] Generating video via Freepik...');
    videoUrl = await generateVideo(serif);
    console.log(`[Step 3] Video URL: ${videoUrl}`);
    await updateCell(sheets, rowNumber, COL.IMAGE_PROMPT, videoUrl);
  } catch (err) {
    const statusMsg = err.message.startsWith('error:') ? err.message : 'error';
    console.error('[Step 3] Error:', err.message);
    await updateCell(sheets, rowNumber, COL.STATUS, statusMsg);
    return;
  }

  // Step 4: Generate caption & hashtags (Claude)
  try {
    console.log('[Step 4] Generating caption and hashtags via Claude...');
    captionData = await generateCaption(topic, serif);
    console.log(`[Step 4] Caption: ${captionData.caption}`);
    await updateCell(sheets, rowNumber, COL.JA_CAPTION, captionData.caption);
    await updateCell(sheets, rowNumber, COL.HASHTAGS, captionData.hashtags);
  } catch (err) {
    console.error('[Step 4] Error:', err.message);
    await updateCell(sheets, rowNumber, COL.STATUS, 'error');
    return;
  }

  // Step 5: Download video and post to SNS
  try {
    console.log('[Step 5] Downloading video...');
    await downloadVideo(videoUrl);

    console.log('[Step 5] Posting to Instagram Reels...');
    await postToInstagram(videoUrl, captionData.caption, captionData.hashtags);

    console.log('[Step 5] Posting to TikTok...');
    await postToTikTok(captionData.caption, captionData.hashtags);
  } catch (err) {
    console.error('[Step 5] Error:', err.message);
    await updateCell(sheets, rowNumber, COL.STATUS, 'error');
    if (fs.existsSync(TMP_VIDEO_PATH)) fs.unlinkSync(TMP_VIDEO_PATH);
    return;
  }

  // Step 6: Mark complete and clean up
  await updateCell(sheets, rowNumber, COL.STATUS, 'done');
  if (fs.existsSync(TMP_VIDEO_PATH)) fs.unlinkSync(TMP_VIDEO_PATH);
  console.log('[Step 6] Pipeline completed successfully.');
  console.log('=== Chinnanago Pipeline End ===');
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
