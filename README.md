# Autotag PDF document using Paddle and PDFix SDK

Docker image-based autotagging of PDF documents with PaddleX and PDFix SDK

## Table of Contents

- [Autotag PDF document using Paddle and PDFix SDK](#autotag-paddle)
  - [Table of Contents](#table-of-contents)
  - [Getting Started](#getting-started)
  - [Run a Docker image ](#run-docker-image)
    - [Run docker container for autotagging](#run-docker-container-autotagging)
    - [Run docker container for template json creation](#run-docker-container-template)
    - [Run docker container for formula description in MathML version 3](#run-docker-container-formula)
    - [Exporting PDFix Configuration for Integration](#export-config-json-integration)
  - [License \& libraries used](#license)
  - [Help \& Support](#help-support)


## Getting Started

To use this Docker application, you'll need to have Docker installed on your system. If Docker is not installed, please follow the instructions on the [official Docker website](https://docs.docker.com/get-docker/) to install it.

## Run a Docker image

### Run docker container for autotagging
All available arguments for autotagging:

```bash
options:
  --name NAME           PDFix license name
  --key KEY             PDFix license key
  --input INPUT, -i INPUT
                        The input PDF file
  --output OUTPUT, -o OUTPUT
                        The output PDF file
  --model {PP-DocLayout-L,RT-DETR-H_layout_17cls}
                        Choose which paddle model to use: PP-DocLayout-L or RT-DETR-H_layout_17cls
  --zoom ZOOM           Zoom level for the PDF page rendering (default: 2.0)
  --process_formula PROCESS_FORMULA
                        Process formulas in the PDF document using formula model. Default is True.
  --process_table PROCESS_TABLE
                        Process tables in the PDF document using table models. Default is True.
  --threshold_paragraph_title THRESHOLD_PARAGRAPH_TITLE
                        Threshold for paragraph title. Value between 0.0 and 1.0. Default is 0.3.
  --threshold_image THRESHOLD_IMAGE
                        Threshold for image. Value between 0.0 and 1.0. Default is 0.5.
  --threshold_text THRESHOLD_TEXT
                        Threshold for text. Value between 0.0 and 1.0. Default is 0.5.
  --threshold_number THRESHOLD_NUMBER
                        Threshold for number. Value between 0.0 and 1.0. Default is 0.5.
  --threshold_abstract THRESHOLD_ABSTRACT
                        Threshold for abstract. Value between 0.0 and 1.0. Default is 0.5.
  --threshold_content THRESHOLD_CONTENT
                        Threshold for content. Value between 0.0 and 1.0. Default is 0.5.
  --threshold_figure_title THRESHOLD_FIGURE_TITLE
                        Threshold for figure title. Value between 0.0 and 1.0. Default is 0.5.
  --threshold_formula THRESHOLD_FORMULA
                        Threshold for formula. Value between 0.0 and 1.0. Default is 0.3.
  --threshold_table THRESHOLD_TABLE
                        Threshold for table. Value between 0.0 and 1.0. Default is 0.5.
  --threshold_table_title THRESHOLD_TABLE_TITLE
                        Threshold for table title. Value between 0.0 and 1.0. Default is 0.5.
  --threshold_reference THRESHOLD_REFERENCE
                        Threshold for reference. Value between 0.0 and 1.0. Default is 0.5.
  --threshold_doc_title THRESHOLD_DOC_TITLE
                        Threshold for doc title. Value between 0.0 and 1.0. Default is 0.5.
  --threshold_footnote THRESHOLD_FOOTNOTE
                        Threshold for footnote. Value between 0.0 and 1.0. Default is 0.5.
  --threshold_header THRESHOLD_HEADER
                        Threshold for header. Value between 0.0 and 1.0. Default is 0.3.
  --threshold_algorithm THRESHOLD_ALGORITHM
                        Threshold for algorithm. Value between 0.0 and 1.0. Default is 0.5.
  --threshold_footer THRESHOLD_FOOTER
                        Threshold for footer. Value between 0.0 and 1.0. Default is 0.5.
  --threshold_seal THRESHOLD_SEAL
                        Threshold for seal. Value between 0.0 and 1.0. Default is 0.3.
  --threshold_chart_title THRESHOLD_CHART_TITLE
                        Threshold for chart title. Value between 0.0 and 1.0. Default is 0.5.
  --threshold_chart THRESHOLD_CHART
                        Threshold for chart. Value between 0.0 and 1.0. Default is 0.5.
  --threshold_formula_number THRESHOLD_FORMULA_NUMBER
                        Threshold for formula number. Value between 0.0 and 1.0. Default is 0.5.
  --threshold_header_image THRESHOLD_HEADER_IMAGE
                        Threshold for header image. Value between 0.0 and 1.0. Default is 0.3.
  --threshold_footer_image THRESHOLD_FOOTER_IMAGE
                        Threshold for footer image. Value between 0.0 and 1.0. Default is 0.5.
  --threshold_aside_text THRESHOLD_ASIDE_TEXT
                        Threshold for aside text. Value between 0.0 and 1.0. Default is 0.5.
```

For example we want to autotag file `/home/pdfs_in/document.pdf` and output should go to `/home/pdfs_out/tagged.pdf` using zoom `3.0`.

To run the Docker container, you should map directories containing PDF documents to the container (using the `-v` parameter) and pass the paths to the input/output PDF documents inside the running container.

Example:

- Your input PDF document is: `/home/pdfs_in/document.pdf`
- Your output PDF document is: `/home/pdfs_out/tagged.pdf`
- Your zoom level is: `3.0`
- You want to skip formula processing
- Threshold for text should be 60%

The command will look like:

```bash
docker run --rm -v /home/pdfs_in:/data_in -v /home/pdfs_out:/data_out pdfix/pdf-accessibility-paddle:latest tag --name $LICENSE_NAME --key $LICENSE_KEY -i /data_in/document.pdf -o /data_out/tagged.pdf --zoom 3.0 --process_formula False --threshold_text 0.6
```

Explanations:
- you need to map directories into the container like `-v /home/pdfs_in:/data_in`
- you will use these if you have PDFix license: `--name ${LICENSE_NAME} --key ${LICENSE_KEY}`

These arguments are for an account-based PDFix license.
```bash
--name ${LICENSE_NAME} --key ${LICENSE_KEY}
```
Contact support for more information.

### Run docker container for template json creation
This does not process Formulas as currently template json does not support associate files.
This has arguments as tagging only difference is output. Instead of PDF it is JSON with content looking like:

```json
{
    "content": "Template json content as json dictionary"
}
```

If you want to use it in PDFix Desktop you need to extract template_json_content into new JSON file.

So for example we will change:

- Your output PDF is: `/home/out/template.json`

And the command will look like:

```bash
docker run --rm -v /home/pdfs_in:/data_in -v /home/out:/data_out pdfix/pdf-accessibility-paddle:latest template -i /data_in/document.pdf -o /data_out/template.json --zoom 3.0 --threshold_text 0.6
```

### Run docker container for formula description in MathML version 3
A JSON file needs to be prepared with base64-encoded data of the formula image.

Input JSON file expected content:

```json
{
    "image": "<header>,<base64_encoded_image>"
}
```

Output JSON file expected content:

```json
{
    "content": "MathML-3 description of formula"
}
```

Example:

- Your input JSON file is: `/home/data/input.json`
- Your output JSON file is: `/home/data/output.json`

```bash
docker run --rm -v /home/data:/data pdfix/pdf-accessibility-paddle:latest formula -i /data/input.json -o /data/output.json
```

### Exporting PDFix Configuration for Integration
To export the configuration JSON file, use the following command:

```bash
docker run --rm -v $(pwd):/data -w /data pdfix/pdf-accessibility-paddle:latest config -o config.json
```

## License & libraries used
- PDFix SDK - https://pdfix.net/terms
- PaddleX - https://paddlepaddle.github.io/PaddleX

The trial version of the PDFix SDK may apply a watermark on the page and redact random parts of the PDF.

## Help & Support
To obtain a PDFix SDK license or report an issue, please contact us at support@pdfix.net.
For more information visit https://pdfix.net
