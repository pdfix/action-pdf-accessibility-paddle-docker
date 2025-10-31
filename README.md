# Autotag PDF Document Using PaddleX and PDFix SDK

A Dockerized solution for automated PDF tagging using Paddle and PDFix SDK. Supports pdf tagging, pdfix layout template generation, MathML extraction from images, and adding MathML associated files to PDF formula tags.

## Table of Contents

- [Autotag PDF Document Using PaddleX and PDFix SDK](#autotag-pdf-document-using-paddlex-and-pdfix-sdk)
  - [Table of Contents](#table-of-contents)
  - [Getting Started](#getting-started)
  - [Run a Docker Container ](#run-docker-container)
    - [Run Docker Container for Autotagging](#run-docker-container-for-autotagging)
    - [Run Docker Container for Template JSON Creation](#run-docker-container-for-template-json-creation)
    - [Run Docker Container for MathML Version 3 Description of Formula](#run-docker-container-for-mathml-version-three-description-of-formula)
      - [Using Image File for One Formula](#using-image-file-for-one-formula)
      - [Using Tagged PDF Document to Process All Formulas](#using-tagged-pdf-document-to-process-all-formulas)
    - [Exporting PDFix Configuration for Integration](#exporting-pdfix-configuration-for-integration)
  - [License \& Libraries Used](#license-and-libraries-used)
  - [Help \& Support](#help-and-support)


## Getting Started

To use this application, Docker must be installed on the system. If Docker is not installed, please follow the instructions on the [official Docker website](https://docs.docker.com/get-docker/) to install it.
First run will pull the docker image, which may take some time. Make your own image for more advanced use.

## Run a Docker Container

### Run Docker Container for Autotagging

Automatically tags PDF using Paddle and PDFix SDK. Adds MathML as associate file to Formula tags.
All available arguments for autotagging:

```bash
options:
  --name NAME           PDFix license name.
  --key KEY             PDFix license key.
  --input INPUT, -i INPUT
                        The input PDF file.
  --output OUTPUT, -o OUTPUT
                        The output PDF file.
  --model {PP-DocLayout-L,RT-DETR-H_layout_17cls}
                        Choose which paddle model to use: PP-DocLayout-L or RT-DETR-H_layout_17cls.
  --zoom ZOOM           Zoom level for the PDF page rendering (default: 2.0).
  --process_formula PROCESS_FORMULA
                        Process formulas in the PDF document using formula model. Default is True.
  --process_table PROCESS_TABLE
                        Process tables in the PDF document using table models. Default is True.
  --threshold_paragraph_title THRESHOLD_PARAGRAPH_TITLE
                        Threshold for paragraph title. Number between 0.05 and 0.95. Default is 0.3.
  --threshold_image THRESHOLD_IMAGE
                        Threshold for image. Number between 0.05 and 0.95. Default is 0.5.
  --threshold_text THRESHOLD_TEXT
                        Threshold for text. Number between 0.05 and 0.95. Default is 0.5.
  --threshold_number THRESHOLD_NUMBER
                        Threshold for number. Number between 0.05 and 0.95. Default is 0.5.
  --threshold_abstract THRESHOLD_ABSTRACT
                        Threshold for abstract. Number between 0.05 and 0.95. Default is 0.5.
  --threshold_content THRESHOLD_CONTENT
                        Threshold for content. Number between 0.05 and 0.95. Default is 0.5.
  --threshold_figure_title THRESHOLD_FIGURE_TITLE
                        Threshold for figure title. Number between 0.05 and 0.95. Default is 0.5.
  --threshold_formula THRESHOLD_FORMULA
                        Threshold for formula. Number between 0.05 and 0.95. Default is 0.3.
  --threshold_table THRESHOLD_TABLE
                        Threshold for table. Number between 0.05 and 0.95. Default is 0.5.
  --threshold_table_title THRESHOLD_TABLE_TITLE
                        Threshold for table title. Number between 0.05 and 0.95. Default is 0.5.
  --threshold_reference THRESHOLD_REFERENCE
                        Threshold for reference. Number between 0.05 and 0.95. Default is 0.5.
  --threshold_doc_title THRESHOLD_DOC_TITLE
                        Threshold for doc title. Number between 0.05 and 0.95. Default is 0.5.
  --threshold_footnote THRESHOLD_FOOTNOTE
                        Threshold for footnote. Number between 0.05 and 0.95. Default is 0.5.
  --threshold_header THRESHOLD_HEADER
                        Threshold for header. Number between 0.05 and 0.95. Default is 0.3.
  --threshold_algorithm THRESHOLD_ALGORITHM
                        Threshold for algorithm. Number between 0.05 and 0.95. Default is 0.5.
  --threshold_footer THRESHOLD_FOOTER
                        Threshold for footer. Number between 0.05 and 0.95. Default is 0.5.
  --threshold_seal THRESHOLD_SEAL
                        Threshold for seal. Number between 0.05 and 0.95. Default is 0.3.
  --threshold_chart_title THRESHOLD_CHART_TITLE
                        Threshold for chart title. Number between 0.05 and 0.95. Default is 0.5.
  --threshold_chart THRESHOLD_CHART
                        Threshold for chart. Number between 0.05 and 0.95. Default is 0.5.
  --threshold_formula_number THRESHOLD_FORMULA_NUMBER
                        Threshold for formula number. Number between 0.05 and 0.95. Default is 0.5.
  --threshold_header_image THRESHOLD_HEADER_IMAGE
                        Threshold for header image. Number between 0.05 and 0.95. Default is 0.3.
  --threshold_footer_image THRESHOLD_FOOTER_IMAGE
                        Threshold for footer image. Number between 0.05 and 0.95. Default is 0.5.
  --threshold_aside_text THRESHOLD_ASIDE_TEXT
                        Threshold for aside text. Number between 0.05 and 0.95. Default is 0.5.
```

To run the Docker container, map directories containing PDF documents to the container (using the `-v` parameter) and pass the paths to the input/output PDF documents inside the running container.

Example:
To create a command for autotagging the file `/home/pdfs_in/document.pdf` and output to `/home/pdfs_out/tagged.pdf`, using a zoom level of `3.0`, with formula processing disabled and an increased threshold for text detection:

Arguments:
- Input PDF document is: `/home/pdfs_in/document.pdf`
- Output PDF document is: `/home/pdfs_out/tagged.pdf`
- Zoom level is: `3.0` (three times the original)
- Formula processing: `off`
- The threshold for text detection: `60%`

Result:

```bash
docker run --rm -v /home/pdfs_in:/data_in -v /home/pdfs_out:/data_out pdfix/pdf-accessibility-paddle:latest tag --name $LICENSE_NAME --key $LICENSE_KEY -i /data_in/document.pdf -o /data_out/tagged.pdf --zoom 3.0 --process_formula False --threshold_text 0.6
```

Explanation:
- Map local directories to the container using `-v` option: `-v /home/pdfs_in:/data_in`

These arguments are for an account-based PDFix license.

```bash
--name ${LICENSE_NAME} --key ${LICENSE_KEY}
```

Contact support for more information.

### Run Docker Container for Template JSON Creation

Automatically creates layout template json using Paddle, saving it as JSON file.
Formula processing is not supported in this mode because the template JSON does not support associated files.
The arguments are the same as for autotagging; the only difference is that the output is a JSON file containing template for autotagging.

Example:
To create a command for template creation with similar arguments as for tagging::

Arguments:
- Input PDF document is: `/home/pdfs_in/document.pdf`
- Output PDF document is: `/home/out/template.json`
- Zoom level is: `3.0` (three times the original)
- The threshold for text detection: `60%`

Result:

```bash
docker run --rm -v /home/pdfs_in:/data_in -v /home/out:/data_out pdfix/pdf-accessibility-paddle:latest template -i /data_in/document.pdf -o /data_out/template.json --zoom 3.0 --threshold_text 0.6
```

### Run Docker Container for MathML Version 3 Description of Formula

This section includes two main actions:
- Get MathML representation of one formula
- Set associated files for all formulas inside PDF document

#### Using Image File for One Formula

Automatically generates MathML from an image file using Paddle, saving it as an XML file.

Example:
To create a command for processing a single formula:

Arguments:
- Input Image file is: `/home/data/input.jpg`
- Output XML file is: `/home/data/output.xml`

Result:

```bash
docker run --rm -v /home/data:/data pdfix/pdf-accessibility-paddle:latest mathml -i /data/input.jpg -o /data/output.xml
```

#### Using Tagged PDF Document to Process All Formulas

Automatically generates MathML for Formula tags using Paddle, attaching it as an associated file to each tag.
This is usefull in case formulas processing was disabled during autotagging.
The PDF document must be tagged, as only `Formula tags` are processed by this command.

Example:
To create a command for processing all formulas in PDF document:

Arguments:
- Input PDF document is: `/home/pdfs_in/document.pdf`
- Output PDF document is: `/home/pdfs_out/tagged.pdf`

Result:

```bash
docker run --rm -v /home/pdfs_in:/data_in -v /home/pdfs_out:/data_out pdfix/pdf-accessibility-paddle:latest mathml --name $LICENSE_NAME --key $LICENSE_KEY -i /data_in/document.pdf -o /data_out/tagged.pdf
```

### Exporting PDFix Configuration for Integration

Command for exporting the configuration JSON file:

```bash
docker run --rm -v $(pwd):/data -w /data pdfix/pdf-accessibility-paddle:latest config -o config.json
```

## License & Libraries Used

- PDFix SDK - https://pdfix.net/terms
- PaddleX - https://paddlepaddle.github.io/PaddleX

The trial version of the PDFix SDK may apply watermarks and redact random content in the output PDF.

## Help & Support

To obtain a PDFix SDK license or report an issue, please contact us at support@pdfix.net.
For more information, visit https://pdfix.net
