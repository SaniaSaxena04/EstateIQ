FROM python:3.10-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose Hugging Face default port
EXPOSE 7860

# Run Flask using Gunicorn on port 7860
CMD ["gunicorn", "-b", "0.0.0.0:7860", "--workers=2", "--threads=4", "app:app"]