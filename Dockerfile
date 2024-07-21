# Use the official Debian slim image as a base
FROM debian:stable-slim

# Install Paddle OCR and necessary dependencies
RUN apt-get update && \
    apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-opencv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/paddle-ocr/

ENV VIRTUAL_ENV=venv


# Create a virtual environment and install dependencies
RUN python3 -m venv venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"


# Copy the source code
COPY src/ /usr/paddle-ocr/src/
# Copy models
COPY models/ /usr/paddle-ocr/models/
# Copy requirements.txt
COPY requirements.txt /usr/paddle-ocr/

# Copy font
COPY src/simfang.ttf /usr/paddle-ocr/


RUN pip install --no-cache-dir -r requirements.txt


ENTRYPOINT ["venv/bin/python3", "src/main.py"]
