"""yt-dlp backend. Run: pip install flask flask-cors yt-dlp ; (ffmpeg must be installed)
   YTDLP_TOKEN=yourSecret python server.py
Optional: YTDLP_COOKIES=/path/cookies.txt (exported from your browser) if a site demands login/bot check."""
import os, glob, shutil, tempfile
from flask import Flask, request, jsonify, send_file, after_this_request, abort
from flask_cors import CORS
import yt_dlp

TOKEN = os.environ.get("YTDLP_TOKEN", "")
COOKIES = os.environ.get("YTDLP_COOKIES", "")
app = Flask(__name__)
CORS(app)

def check():
    if TOKEN and request.args.get("token") != TOKEN:
        abort(401)

def base_opts():
    o = {"quiet": True, "noplaylist": True}
    if COOKIES and os.path.exists(COOKIES):
        o["cookiefile"] = COOKIES
    return o

@app.get("/api/info")
def info():
    check()
    try:
        with yt_dlp.YoutubeDL(base_opts()) as y:
            d = y.extract_info(request.args.get("url", ""), download=False)
    except Exception as e:
        return jsonify(error=str(e)), 400
    heights = sorted({f["height"] for f in d.get("formats", [])
                      if f.get("height") and f.get("vcodec") != "none"}, reverse=True)
    return jsonify(title=d.get("title"), thumbnail=d.get("thumbnail"),
                   uploader=d.get("uploader"), duration=d.get("duration"), heights=heights)

@app.get("/api/download")
def download():
    check()
    url = request.args.get("url", "")
    mode = request.args.get("mode", "video")
    h = request.args.get("height", "")
    tmp = tempfile.mkdtemp()
    o = base_opts()
    o["outtmpl"] = os.path.join(tmp, "%(title).150B.%(ext)s")
    if mode == "audio":
        o["format"] = "bestaudio/best"
        o["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
    else:
        o["format"] = f"bv*[height<={h}]+ba/b[height<={h}]" if h.isdigit() else "bv*+ba/b"
        o["merge_output_format"] = "mp4"
    try:
        with yt_dlp.YoutubeDL(o) as y:
            y.download([url])
        f = glob.glob(os.path.join(tmp, "*"))[0]
    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        return jsonify(error=str(e)), 400

    @after_this_request
    def cleanup(r):
        r.call_on_close(lambda: shutil.rmtree(tmp, ignore_errors=True))
        return r
    return send_file(f, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
