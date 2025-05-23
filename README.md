# Autotag PDF document using Paddle and PDFix SDK

Docker image-based autotagging of PDF documents with PaddleX and PDFix SDK

## Table of Contents

- [Autotag PDF document using Paddle and PDFix SDK](#autotag-paddle)
  - [Table of Contents](#table-of-contents)
  - [Getting Started](#getting-started)
  - [Run a Docker image ](#run-docker-image)
    - [Run docker container for autotagging](#run-docker-container-autotagging)
    - [Run docker container for template json creation](#run-docker-container-template)
    - [Run docker container for formula description in latex](#run-docker-container-formula)
    - [Exporting PDFix Configuration for Integration](#export-config-json-integration)
  - [License \& libraries used](#license)
  - [Help \& Support](#help-support)


## Getting Started

To use this Docker application, you'll need to have Docker installed on your system. If Docker is not installed, please follow the instructions on the [official Docker website](https://docs.docker.com/get-docker/) to install it.

## Run a Docker image

### Run docker container for autotagging
To run the Docker container, you should map directories containing PDF documents to the container (using the `-v` parameter) and pass the paths to the input/output PDF documents inside the running container.

Example: 

- Your input PDF is: `/home/pdfs_in/document.pdf`
- Your output PDF is: `/home/pdfs_out/tagged.pdf`

The path `/home/pdfs_in` is mapped to `/data_in`, and `/home/pdfs_out` is mapped to `/data_out`

There are two layout models in Paddle:
- "PP-DocLayout-L" - recognises 23 classes
- "RT-DETR-H_layout_17cls" - recognises 17 classes

You can choose either of them using the optional `--model` argument. By default "PP-DocLayout-L" is used.

Rendering of page into image for Paddle engine is controlled by argument `--zoom` which takes number.
Most sence take numbers between 1.0 and 4.0.

These arguments are for an account-based PDFix license.
```bash
--name ${LICENSE_NAME} --key ${LICENSE_KEY}
```
Contact support for more information.

The command will look like:

```bash
docker run --rm -v /home/pdfs_in:/data_in -v /home/pdfs_out:/data_out pdfix/pdf-accessibility-paddle:latest tag --name $LICENSE_NAME --key $LICENSE_KEY --input /data_in/document.pdf --output /data_out/tagged.pdf --model PP-DocLayout-L --zoom 2.0
```

### Run docker container for template json creation
This is similar to running tagging. Difference is output file. Here it is JSON.

Example:

- Your output PDF is: `/home/out/template.json`

```bash
docker run --rm -v /home/pdfs_in:/data_in -v /home/out:/data_out pdfix/pdf-accessibility-paddle:latest template --input /data_in/document.pdf --output /data_out/template.json --model PP-DocLayout-L --zoom 2.0
```

### Run docker container for formula description in latex
A JSON file needs to be prepared with base64-encoded data of the formula image.

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

The trial version of the PDFix SDK may apply a watermark on the page and redact random parts of the PDF.

## Help & Support
To obtain a PDFix SDK license or report an issue, please contact us at support@pdfix.net.
For more information visit https://pdfix.net
