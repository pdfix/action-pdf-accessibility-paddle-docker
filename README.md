# PDFix OCR with Paddle 

Docker image based PDF text recogntion with PaddleX and PDFix SDK

## System Requirements
- Docker Engine https://docs.docker.com/engine/install/

## Run a Docker image 

### Build docker image
Build the docker image with the name `pdfix-paddlex`. You can choose another name if you want.
Build downloads models that can be used and fonts that PaddleX requires and would normaly download for each container run.

```
docker build -t pdfix-paddlex .
```

### Run docker container
To run docker container you should map directories with PDF documents to the container (`-v` parameter) and pass paths to input/output PDF document in the running container

Example: 

- Your input PDF is: `/home/pdfs_in/scanned.pdf`
- Your output PDF is: `/home/pdfs_out/ocred.pdf`

Path `/home/pdfs_in` is mapped to `/data_in` and `/home/pdfs_out` is mapped to `/data_out`

```
docker run --rm -v /home/pdfs_in:/data_in -v /home/pdfs_out:/data_out -it pdfix-paddlex --name $LICENSE_NAME --key $LICENSE_KEY tag --input /data_in/scanned.pdf --output /data_out/ocred.pdf
```
Arguments `--input`, `--output`, `--name`, `--key` are the same as the CLI.
Argument `tag` says that pdf should be autotaged.
Argument `config` can be used instead and that just prints or copies `config.json`.

### Run docker container with visual output from models
Running debug docker is similar as running docker normaly. One additional mount is required for `/usr/paddlex/output`.

Example:

- Your folder where images with recognised layout is : `/home/output`

```
docker run --rm -v /home/pdfs_in:/data_in -v /home/pdfs_out:/data_out -v /home/output:/usr/paddlex/output -it pdfix-paddlex --name $LICENSE_NAME --key $LICENSE_KEY tag --input /data_in/scanned.pdf --output /data_out/ocred.pdf
```

### Running code outside of docker
As code contains relative paths for models you need to download models by hand into `models` folder.
This can be done for example by using link from Dockerfile.

## License & libraries used
- PDFix SDK - https://pdfix.net/terms
- PaddleX - https://paddlepaddle.github.io/PaddleX

Trial version of the PDFix SDK may apply a watermark on the page and redact random parts of the PDF.

## Help & Support
To obtain a PDFix SDK license or report an issue please contact us at support@pdfix.net.
For more information visit https://pdfix.net
