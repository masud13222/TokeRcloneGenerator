FROM python:3.10-slim-buster

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    mediainfo \
    libmediainfo0v5 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp globally
RUN pip install -U yt-dlp

COPY . .
RUN pip install -r requirements.txt

# Expose port 8080
EXPOSE 8080
CMD ["python", "bot.py"] 