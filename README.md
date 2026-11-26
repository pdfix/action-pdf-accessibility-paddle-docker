# PDF Accessibility Paddle

Uses PaddleX models for layout and formula recognition, running fully offline. For PDF output without watermarks, a **PDFix SDK** license is required.

## Table of Contents

- [PDF Accessibility Paddle](#pdf-accessibility-paddle)
  - [Getting started](#getting-started)
  - [Usage](#usage)
  - [Commands](#commands)
  - [Arguments](#arguments)
  - [Params JSON](#params-json)
  - [How it works](#how-it-works)
  - [Exit codes](#exit-codes)
  - [Examples](#examples)
  - [Help \& support](#help--support)
  - [Licenses](#licenses)

## Getting started

You need Docker installed. The first run downloads the image and may take longer than later runs.

## Usage

Mount a folder into the container and run a subcommand:

```bash
docker run --rm -v "$(pwd)":/data -w /data pdfix/pdf-accessibility-paddle:latest <command> [options]
```

## Commands

- `tag`: Autotag a PDF (PDF → PDF)
- `template`: Create a layout template JSON (PDF → JSON)
- `mathml`: MathML from formulas in a PDF or from a formula image (PDF → PDF or image → XML)

## Arguments

### Common (`tag` / `template`)

| Option | Required | Type / expected value | Description |
|---|:---:|---|---|
| `--input`, `-i` | yes | Path to an existing `.pdf` file | Input PDF |
| `--output`, `-o` | yes | Path for `.pdf`/`.json` depending on command | Output file |
| `--name` | no | String (PDFix account license name) | PDFix license name |
| `--key` | no | String (PDFix account license key) | PDFix license key |
| `--model` | no | `PP-DocLayout-L` or `RT-DETR-H_layout_17cls` (default: `PP-DocLayout-L`) | Layout model |
| `--zoom` | no | Float, range **1.0–4.0** (default **2.0**) | Page render zoom |
| `--process_table` | no | Boolean string (default: `true`) | Process tables |

### `tag` only

| Option | Required | Type / expected value | Description |
|---|:---:|---|---|
| `--process_formula` | no | Boolean string (default: `true`) | Process formulas |

### Threshold options (`tag` / `template`)

Each value is clamped to **0.05–0.95**; a clamped value is logged as a warning.

| Option | Default | Type / expected value |
|---|:---:|---|
| `--threshold_paragraph_title` | 0.3 | Float |
| `--threshold_image` | 0.5 | Float |
| `--threshold_text` | 0.5 | Float |
| `--threshold_number` | 0.5 | Float |
| `--threshold_abstract` | 0.5 | Float |
| `--threshold_content` | 0.5 | Float |
| `--threshold_figure_title` | 0.5 | Float |
| `--threshold_formula` | 0.3 | Float |
| `--threshold_table` | 0.5 | Float |
| `--threshold_table_title` | 0.5 | Float |
| `--threshold_reference` | 0.5 | Float |
| `--threshold_doc_title` | 0.5 | Float |
| `--threshold_footnote` | 0.5 | Float |
| `--threshold_header` | 0.3 | Float |
| `--threshold_algorithm` | 0.5 | Float |
| `--threshold_footer` | 0.5 | Float |
| `--threshold_seal` | 0.3 | Float |
| `--threshold_chart_title` | 0.5 | Float |
| `--threshold_chart` | 0.5 | Float |
| `--threshold_formula_number` | 0.5 | Float |
| `--threshold_header_image` | 0.3 | Float |
| `--threshold_footer_image` | 0.5 | Float |
| `--threshold_aside_text` | 0.5 | Float |

### `mathml`

| Option | Required | Type / expected value | Description |
|---|:---:|---|---|
| `--input`, `-i` | yes | Path to `.pdf` or supported image file | Input |
| `--output`, `-o` | yes | Path to `.pdf` or `.xml` matching mode | Output |
| `--params` | for PDF → PDF | Path to a `.json` file | Tag filter parameters (see [Params JSON](#params-json)) |
| `--overwrite` | no | Boolean string (default: `false`) | PDF → PDF only: replace an existing MathML associated file whose file name contains `mathml-3` |
| `--name` | no | String (PDFix license); use for PDF → PDF without watermarks | PDFix license name |
| `--key` | no | String (PDFix license); use for PDF → PDF without watermarks | PDFix license key |

Default tag filter when `--params` is omitted: `Formula`.

## Params JSON

`--params` points to a JSON array of parameter objects. Each object has at least `name` and `value`; the CLI reads those fields to decide which tags to process (PDF → PDF `mathml` only).

### `tag_names`

`tag_names` is an ECMAScript regular expression matching tag names, or a template `tag_update` object.

Example (`example/params_mathml.json`) — match `Formula` tags:

```json
[
    {
        "title": "Tags",
        "desc": "Specify the tags using a ECMAScript regular expression or define them by template tag_update",
        "name": "tag_names",
        "type": "tag",
        "value": "Formula",
        "values": [
            {
                "desc": "All tags",
                "value": ".*"
            }
        ]
    }
]
```

Use `"value": ".*"` to match all tags.

## How it works

- **Existing tags are replaced.** `tag` removes the structure tree and all tags of the document, then tags it from the detected layout.
- **Regions → tags:** text → `P`; every paragraph title → heading `H1` (Paddle gives no heading levels); document title → `Title`; figure, table and chart titles → `Caption`; images and charts → `Figure`; tables keep rows, columns and spans (`--process_table`); formulas → `Formula`; headers, footers, header and footer images, page numbers, aside text and seals → artifacts.
- **Formulas:** `tag` with `--process_formula` and `mathml` add the recognized formula as MathML 3 associated file (AF) to each `Formula` tag: file `mathml-3.xml`, AFRelationship `Supplement`, subtype `application/mathml+xml`, created by PDFix SDK like in PDFix Desktop. The MathML is wrapped in `semantics` with the annotation `Generated by Paddle`. `Formula` tags get no alternate text. When no formula is recognized, the existing MathML is kept and a warning is logged. The image mode fails with error 31 only when nothing is recognized; a blank image can still give a formula such as `=`.
- **Rendering:** pages (and formulas for `mathml`, at zoom 1) are rendered as JPG files `paddle_page_<n>.jpg` / `formula_<id>.jpg` into the working folder and deleted after they are read.
- **Checks before processing:** output extension (16) and folder (13), input (14 / 15), zoom (17), params (12), then the license.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Unexpected error (`Failed to run the program:` + traceback) |
| 10 | Invalid arguments or no command |
| 11 | Invalid regex or template in `tag_names` |
| 12 | Missing or invalid params file / parameters |
| 13 | Output folder does not exist |
| 14 | Input file is not an existing PDF |
| 15 | Input file is not an existing image (JPG, JPEG, PNG or BMP) |
| 16 | Wrong output extension (`.pdf` for `tag`, `.json` for `template`, `.pdf` or `.xml` for `mathml`) |
| 17 | Zoom is not between 1.0 and 4.0 |
| 20–29 | PDFix SDK errors (20 initialize, 21 activate, 22 authorize, 23 render, 24 open, 25 save, 26 tag, 27 template, 28 no tags, 29 load template); the SDK error is logged on its own line |
| 30 | Image file cannot be read |
| 31 | No formula was recognized in the image |

## Examples

Tag a PDF:

```bash
docker run --rm -v "$(pwd)":/data -w /data pdfix/pdf-accessibility-paddle:latest \
  tag --name "${LICENSE_NAME}" --key "${LICENSE_KEY}" \
  -i /data/input.pdf -o /data/tagged.pdf --zoom 3.0 --process_formula false --threshold_text 0.6
```

Create a layout template JSON:

```bash
docker run --rm -v "$(pwd)":/data -w /data pdfix/pdf-accessibility-paddle:latest \
  template -i /data/input.pdf -o /data/template.json --zoom 3.0 --threshold_text 0.6
```

MathML for Formula tags in a PDF:

```bash
docker run --rm -v "$(pwd)":/data -w /data pdfix/pdf-accessibility-paddle:latest \
  mathml --name "${LICENSE_NAME}" --key "${LICENSE_KEY}" \
  -i /data/input.pdf -o /data/output.pdf --params /data/example/params_mathml.json
```

MathML from one formula image:

```bash
docker run --rm -v "$(pwd)":/data -w /data pdfix/pdf-accessibility-paddle:latest \
  mathml -i /data/formula.jpg -o /data/formula.xml
```

## Help & support

For PDFix SDK licensing or issues, contact `support@pdfix.net`.

## Licenses

- [PDFix Terms](https://pdfix.net/terms)
- [PaddleX](https://github.com/PaddlePaddle/PaddleX) — [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0) (also the bundled PaddleX models)
- [latex2mathml](https://github.com/roniemartinez/latex2mathml) — MIT
- [OpenCV](https://github.com/opencv/opencv-python) — [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0)
