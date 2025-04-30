# Use the official Debian slim image with python 3.12 as a base
FROM python:3.12-slim

# Update system and Install python3
RUN apt-get update && \
    apt-get install -y \
    python3-pip \
    python3-venv \
    python3-opencv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/paddlex/


# Create a virtual environment and install paddle and dependencies
ENV VIRTUAL_ENV=venv
RUN python3.12 -m venv venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
COPY requirements.txt /usr/paddlex/
RUN pip3 install --no-cache-dir -r requirements.txt


# Copy models, config, source code, ...
# TODO need another modelsCOPY models/ /usr/paddlex/models/
COPY config.json /usr/paddlex/
COPY src/ /usr/paddlex/src/
COPY output/ /usr/paddlex/output/


ENTRYPOINT ["/usr/paddlex/venv/bin/python3", "/usr/paddlex/src/main.py"]
