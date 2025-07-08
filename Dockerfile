# Python official slim image
FROM python:3.11-slim

# Update ও ffmpeg install (ffmpeg লাগে ভিডিও মার্জের জন্য)
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

# কাজের ডিরেক্টরি সেট করো
WORKDIR /app

# requirements ফাইল কপি করে ইনস্টল করো
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# বাকি ফাইল কপি করো
COPY . .

# render.com এর জন্য পোর্ট এক্সপোজ করো
EXPOSE 5000

# অ্যাপ চালানোর কমান্ড
CMD ["python", "app.py"]
