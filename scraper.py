import os
import re
import json
import random
import requests
from flask import Flask, request, jsonify
from urllib.parse import unquote
from datetime import datetime

app = Flask(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
]

def extract_video_id(url):
    match = re.search(r'/video/(\d+)', url)
    if match:
        return match.group(1)
    if url.isdigit():
        return url
    return None

def extract_views_from_html(html):
    # Try JSON script first
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

    # Fallback to original regex patterns
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
    video_id = extract_video_id(video_url)
    if not video_id:
        return jsonify({"error": "Invalid TikTok URL"}), 400

    # Use the same URL format as your original working bot
    fetch_url = f"https://www.tiktok.com/@any/video/{video_id}"
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        resp = requests.get(fetch_url, headers=headers, timeout=15, allow_redirects=True)
        html = resp.text

        views = extract_views_from_html(html)
        if views is not None:
            return jsonify({"views": views})
        else:
            return jsonify({"error": "View count not found"}), 404
    except Exception as e:
        app.logger.error(f"Error fetching views: {e}")
        return jsonify({"error": "Failed to retrieve video data"}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
