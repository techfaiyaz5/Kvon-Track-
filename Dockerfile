# Python image uthao
FROM python:3.9-slim

# Camera aur GUI processing ke liye system dependencies
RUN apt-get update && apt-get install -y libgl1 libglib2.0-0
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Work directory set karo
WORKDIR /app

# Requirements file copy aur install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pura project copy karo
COPY . .

# Flask port
EXPOSE 5000

# App chalao
CMD ["python", "app.py"]