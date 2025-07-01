# Use cached image so build is faster
FROM pdfix/pdf-accessibility-paddle-cache:v0.0.1


# Lets install requirements that could have changed from last time we built the cached image
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


# Create required folders
RUN mkdir -p /usr/paddlex/output \
    && mkdir -p /data

# Copy config and sources
COPY config.json /usr/paddlex/
COPY src/ /usr/paddlex/src/


ENTRYPOINT ["/usr/paddlex/venv/bin/python3", "/usr/paddlex/src/main.py"]
