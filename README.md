# PDFix OCR with Paddle 

Docker image based PDF text recogntion with OCR Paddle and PDFix SDK

## System Requirements
- Docker Engine https://docs.docker.com/engine/install/

## Run a Docker image 

### Build docker image
Build the docker image with the name `pdfix-paddle-ocr`. You can choose another name if you want.

```
docker build -t pdfix-paddle-ocr .
```

### Run docker container
To run docker container you should map directories with PDF documents to the container (`-v` parameter) and pass paths to input/output PDF document in the running container

Example: 

- Your input PDF is: `/home/pdfs_in/scanned.pdf`
- Your output PDF is: `/home/pdfs_out/ocred.pdf`

Path `/home/pdfs_in` is mapped to `/data_in` and `/home/pdfs_out` is mapped to `/data_out`

```
docker run --rm -v /home/pdfs_in:/data_in -v /home/pdfs_out:/data_out -it pdfix-paddle-ocr --name $LICENSE_NAME --key $LICENSE_KEY tag --input /data_in/scanned.pdf --output /data_out/ocred.pdf
```
Arguments `--input`, `--output`, `--name`, `--key` are the same as the CLI.
Argument `tag` says that pdf should be autotaged.
Argument `config` can be used instead and that just prints or copies `config.json`.

### Run debug docker container
To add debug features you need to share folders to container:
- source code is located in `/usr/paddle-ocr/src`
- folder for image outputs where bboxes recognized by paddle are visualized is located at `/usr/paddle-ocr/images-1.0`

In example under this your development code is located in `/home/src` and after run you will see what paddle recognised in `/home/pdf-images`.
Both folders need to exists before running docker.

```
docker run --rm -v /home/pdfs_in:/data_in -v /home/pdfs_out:/data_out -v /home/src:/usr/paddle-ocr/src -v /home/pdf-images:/usr/paddle-ocr/images-1.0 -it tag pdfix-paddle-ocr --input /data_in/scanned.pdf --output /data_out/ocred.pdf --lang eng --name $LICENSE_NAME --key $LICENSE_KEY
```

## License & libraries used
- PDFix SDK - https://pdfix.net/terms
- OCR Paddle - https://github.com/PaddlePaddle/PaddleOCR

Trial version of the PDFix SDK may apply a watermark on the page and redact random parts of the PDF.

## Help & Support
To obtain a PDFix SDK license or report an issue please contact us at support@pdfix.net.
For more information visit https://pdfix.net

