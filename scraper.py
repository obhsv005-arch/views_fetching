import os
import re
import json
import random
import time
import requests
from flask import Flask, request, jsonify
from urllib.parse import unquote, urlparse
from datetime import datetime

app = Flask(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
]

def extract_video_id_and_username(url):
    """Extract video ID and optionally username from a TikTok URL."""
    # Try to find both username and video ID
    match = re.search(r'@([\w\.]+)/video/(\d+)', url)
    if match:
        return match.group(2), match.group(1)  # video_id, username
    # If only video ID is present
    match = re.search(r'/video/(\d+)', url)
    if match:
        return match.group(1), None
    if url.isdigit():
        return url, None
    return None, None

def extract_views_from_html(html):
    """Multiple methods to extract view count from TikTok HTML."""
    views = None

    # Method 1: Universal data script (most reliable)
    script_pattern = r'<script id="__UNIVERSAL_DATA_FOR_LAYOUT__"[^>]*>(.*?)</script>'
    match = re.search(script_pattern, html, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(1))
            stats = data['__DEFAULT_SCOPE__']['webapp.video-detail']['itemInfo']['itemStruct']['stats']
            views = stats.get('playCount') or stats.get('viewCount')
            if views is not None:
                return int(views)
        except (KeyError, json.JSONDecodeError, TypeError):
            pass

    # Method 2: Scan all script tags for JSON containing playCount/viewCount
    script_tags = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
    for script in script_tags:
        script = script.strip()
        if script.startswith('{') or script.startswith('['):
            try:
                data = json.loads(script)
                # Recursively search for a key named 'playCount' or 'viewCount'
                def find_count(obj):
                    if isinstance(obj, dict):
                        if 'playCount' in obj:
                            return obj['playCount']
                        if 'viewCount' in obj:
                            return obj['viewCount']
                        for v in obj.values():
                            res = find_count(v)
                            if res is not None:
                                return res
                    elif isinstance(obj, list):
                        for item in obj:
                            res = find_count(item)
                            if res is not None:
                                return res
                    return None
                count = find_count(data)
                if count is not None:
                    return int(count)
            except json.JSONDecodeError:
                continue

    # Method 3: Original regex patterns on the whole HTML
    patterns = [
        r'"playCount":(\d+)',
        r'"playCount"\s*:\s*(\d+)',
        r'"viewCount"\s*:\s*(\d+)',
        r'"view_count"\s*:\s*(\d+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return int(match.group(1))

    return None

@app.route('/')
def home():
    return jsonify({
        "service": "TikTok View Scraper",
        "status": "running",
        "endpoints": {
            "/api/views?url=...": "Get view count for a TikTok video",
            "/health": "Health check"
        }
    })

@app.route('/api/views', methods=['GET'])
def get_views():
    url_param = request.args.get('url')
    if not url_param:
        return jsonify({"error": "Missing url parameter"}), 400

    video_url = unquote(url_param)
    video_id, username = extract_video_id_and_username(video_url)
    if not video_id:
        return jsonify({"error": "Invalid TikTok URL"}), 400

    # Try up to 3 times with different user agents
    max_retries = 3
    for attempt in range(max_retries):
        # Use the real username if available, otherwise fallback to 'any'
        fetch_username = username if username else 'any'
        fetch_url = f"https://www.tiktok.com/@{fetch_username}/video/{video_id}"
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.tiktok.com/",
            "DNT": "1",
        }

        try:
            resp = requests.get(fetch_url, headers=headers, timeout=15, allow_redirects=True)
            if resp.status_code != 200:
                app.logger.warning(f"Attempt {attempt+1}: HTTP {resp.status_code}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # exponential backoff
                    continue
                return jsonify({"error": f"TikTok returned status {resp.status_code}"}), 502

            html = resp.text
            views = extract_views_from_html(html)
            if views is not None:
                return jsonify({"views": views})

            app.logger.warning(f"Attempt {attempt+1}: View count not found in HTML")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return jsonify({"error": "View count not found after multiple attempts"}), 404

        except requests.exceptions.RequestException as e:
            app.logger.error(f"Attempt {attempt+1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return jsonify({"error": "Failed to fetch video page"}), 500

    # Should never reach here, but just in case
    return jsonify({"error": "Unexpected error"}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
