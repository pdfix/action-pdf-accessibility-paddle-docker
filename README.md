# Autotag using Paddle and PDFix SDK

Docker image based autotag PDF with PaddleX and PDFix SDK

## Table of Contents

- [Autotag using Paddle and PDFix SDK](#autotag-paddle)
  - [Table of Contents](#table-of-contents)
  - [Getting Started](#getting-started)
  - [Run a Docker image ](#run-docker-image)
    - [Run docker container for autotagging](#run-docker-container-autotagging)
    - [Run docker container with visual output from models](#run-docker-container-visual-debug)
    - [Run docker container for formula description in latex](#run-docker-container-formula)
    - [Exporting PDFix Configuration for Integration](#export-config-json-integration)
  - [License \& libraries used](#license)
  - [Help \& Support](#help-support)


## Getting Started

To use this Docker application, you'll need to have Docker installed on your system. If Docker is not installed, please follow the instructions on the [official Docker website](https://docs.docker.com/get-docker/) to install it.

## Run a Docker image

### Run docker container for autotagging
To run docker container you should map directories with PDF documents to the container (`-v` parameter) and pass paths to input/output PDF document in the running container

Example: 

- Your input PDF is: `/home/pdfs_in/document.pdf`
- Your output PDF is: `/home/pdfs_out/tagged.pdf`

Path `/home/pdfs_in` is mapped to `/data_in` and `/home/pdfs_out` is mapped to `/data_out`

There are 2 layout models in Paddle:
- PP-DocLayout-L - recognises 23 classes
- RT-DETR-H_layout_17cls - recognises 17 classes

You can choose either of them using `--model` argument.

```bash
docker run --rm -v /home/pdfs_in:/data_in -v /home/pdfs_out:/data_out -it pdfix/pdf-accessibility-paddle:latest --name $LICENSE_NAME --key $LICENSE_KEY tag --model PP-DocLayout-L --input /data_in/document.pdf --output /data_out/tagged.pdf
```

These arguments are for an account-based PDFix License.
```bash
--name ${LICENSE_NAME} --key ${LICENSE_KEY}
```
Contact support for more infomation.


### Run docker container with visual output from models
Running debug docker is similar as running docker normaly. One additional mount is required for `/usr/paddlex/output`.

Example:

- Your folder where images with recognised layout is : `/home/output`

```bash
docker run --rm -v /home/pdfs_in:/data_in -v /home/pdfs_out:/data_out -v /home/output:/usr/paddlex/output -it pdfix/pdf-accessibility-paddle:latest --name $LICENSE_NAME --key $LICENSE_KEY tag --input /data_in/document.pdf --output /data_out/tagged.pdf
```

### Run docker container for formula description in latex
JSON file needs to be prepared with encoded base64 data of formula image.

Example: 

- Your input JSON is: `/home/data/input.json`
- Your output JSON is: `/home/data/output.json`

```bash
docker run --rm -v /home/data:/data -it pdfix/pdf-accessibility-paddle:latest generate_alt_text_formula -i /data/input.json -o /data/output.json
```

### Exporting PDFix Configuration for Integration
To export the configuration JSON file, use the following command:

```bash
docker run -v $(pwd):/data -w /data --rm pdfix/pdf-accessibility-paddle:latest config -o config.json
```

## License & libraries used
- PDFix SDK - https://pdfix.net/terms
- PaddleX - https://paddlepaddle.github.io/PaddleX

Trial version of the PDFix SDK may apply a watermark on the page and redact random parts of the PDF.

## Help & Support
To obtain a PDFix SDK license or report an issue please contact us at support@pdfix.net.
For more information visit https://pdfix.net
