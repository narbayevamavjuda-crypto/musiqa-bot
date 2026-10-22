FROM python:3.12-slim

# ffmpeg — audio uchun; deno — yt-dlp YouTube bilan to'g'ri ishlashi uchun
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg curl unzip ca-certificates \
 && curl -fsSL https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip -o /tmp/deno.zip \
 && unzip /tmp/deno.zip -d /usr/local/bin && rm /tmp/deno.zip \
 && apt-get purge -y unzip && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PYTHONUNBUFFERED=1
# Har ishga tushganda yt-dlp yangilanadi (YouTube tez-tez o'zgaradi)
CMD ["sh", "-c", "pip install -q --no-cache-dir -U 'yt-dlp[default]' ; python bot.py"]
