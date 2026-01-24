FROM python:3.10-slim

# FFmpeg install karne ke liye zaroori commands
RUN apt-get update && apt-get install -y ffmpeg && apt-get clean

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

# Aapki main file ka naam main.py hai toh wahi likhein
CMD ["python", "main.py"]
