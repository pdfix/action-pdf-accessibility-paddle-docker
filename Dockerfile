# Use the official Debian slim image as a base
FROM debian:stable-slim

# Update system and Install python3
RUN apt-get update && \
    apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-opencv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/paddle-ocr/


# Create a virtual environment and install paddle and dependencies
ENV VIRTUAL_ENV=venv
RUN python3 -m venv venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
COPY requirements.txt /usr/paddle-ocr/
RUN pip3 install --no-cache-dir -r requirements.txt


# Copy models, config, source code, ...
COPY models/ /usr/paddle-ocr/models/
COPY config.json /usr/paddle-ocr/
COPY src/ /usr/paddle-ocr/src/
COPY images/ /usr/paddle-ocr/images-1.0/


ENTRYPOINT ["/usr/paddle-ocr/venv/bin/python3", "/usr/paddle-ocr/src/main.py"]
