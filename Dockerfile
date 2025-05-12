# Use the official Debian slim image with python 3.12 as a base (paddlex does not work with python 3.13)
FROM python:3.12-slim

# Update system and Install python3
RUN apt-get update && \
    apt-get install -y \
    python3-pip \
    python3-venv \
    python3-opencv \
    ccache \
    curl \
    unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /usr/paddlex/


# Create a virtual environment and install paddlex and dependencies
ENV VIRTUAL_ENV=venv
RUN python3.12 -m venv venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
COPY requirements.txt /usr/paddlex/
RUN pip3 install --no-cache-dir -r requirements.txt


# Download models from web into "models" folder so they are not downloaded for each container run
RUN models_path=/usr/paddlex/models/ ; \
    mkdir ${models_path} ; \
    for model in PP-DocLayout-L RT-DETR-H_layout_17cls PP-LCNet_x1_0_table_cls RT-DETR-L_wired_table_cell_det RT-DETR-L_wireless_table_cell_det PP-FormulaNet-L; do \
        if [ ! -d ${models_path}/${model} ]; then \
            curl -o ${models_path}${model}.tar https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/${model}_infer.tar ; \
            tar -xf ${models_path}${model}.tar ; \
            mv ${model}_infer ${models_path}${model} ; \
            rm ${models_path}${model}.tar ; \
        fi ; \
    done


# Download fonts from web into "fonts" folder so they are not downloaded for each container run
RUN font_path=/usr/paddlex/venv/lib/python3.12/site-packages/paddlex/utils/fonts/ ; \
    for font in PingFang-SC-Regular.ttf simfang.ttf; do \
        if [ ! -f ${font_path}${font} ]; then \
        curl -o ${font_path}${font} https://paddle-model-ecology.bj.bcebos.com/paddlex/PaddleX3.0/fonts/${font} ; \
        fi ; \
    done


# Copy config for PDFix
COPY config.json /usr/paddlex/

# Copy source code
COPY src/ /usr/paddlex/src/

# Create output folder for debug purposes
RUN mkdir -p output


# update pdfix-sdk to 6.3.0 #TODO build aarch64
RUN curl -o pdfix_sdk-8.6.0.tar.gz.zip -L https://github.com/pdfix/pdfix_sdk_builds/releases/download/v8.6.0-beta-3/python-pdfix_sdk-8.6.0_676a7ab6.tar.gz.zip
RUN unzip pdfix_sdk-8.6.0.tar.gz.zip
RUN pip install pdfix_sdk-8.6.0.tar.gz
RUN rm pdfix_sdk-8.6.0.tar.gz.zip pdfix_sdk-8.6.0.tar.gz


ENTRYPOINT ["/usr/paddlex/venv/bin/python3", "/usr/paddlex/src/main.py"]
