import os
import re
import random
import requests
from flask import Flask, request, jsonify
from urllib.parse import unquote

app = Flask(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
]

def extract_video_id(url):
    """Extract numeric video ID from a TikTok URL."""
    match = re.search(r'/video/(\d+)', url)
    if match:
        return match.group(1)
    if url.isdigit():
        return url
    return None

@app.route('/api/views', methods=['GET'])
def get_views():
    """Endpoint to fetch TikTok video views."""
    url_param = request.args.get('url')
    if not url_param:
        return jsonify({"error": "Missing url parameter"}), 400

    # Decode the URL (sent encoded by main app)
    video_url = unquote(url_param)
    video_id = extract_video_id(video_url)
    if not video_id:
        return jsonify({"error": "Invalid TikTok URL"}), 400

    # Build a generic TikTok video page URL (username doesn't matter)
    fetch_url = f"https://www.tiktok.com/@any/video/{video_id}"
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    try:
        resp = requests.get(fetch_url, headers=headers, timeout=15)
        html = resp.text

        # Common patterns where view count appears in TikTok's HTML/JSON
        patterns = [
            r'"playCount":(\d+)',
            r'"playCount"\s*:\s*(\d+)',
            r'"viewCount"\s*:\s*(\d+)',
            r'"view_count"\s*:\s*(\d+)'
        ]

        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                views = int(match.group(1))
                return jsonify({"views": views})

        return jsonify({"error": "View count not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint (useful for monitoring)."""
    return jsonify({"status": "ok", "timestamp": str(datetime.now())})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))  # Render uses PORT env
    app.run(host='0.0.0.0', port=port)
