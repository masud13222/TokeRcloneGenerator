FROM python:3.9-slim

WORKDIR /app

# Install required packages
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy all files
COPY . .

# Expose port for health check
EXPOSE 8080

# Run bot
CMD ["python", "bot.py"] 