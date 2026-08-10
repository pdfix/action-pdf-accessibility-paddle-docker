# PDF Accessibility Paddle

Uses PaddleX models for layout and formula recognition, running fully offline. For PDF output without watermarks, a **PDFix SDK** license is required.

## Table of Contents

- [PDF Accessibility Paddle](#pdf-accessibility-paddle)
  - [Getting started](#getting-started)
  - [Usage](#usage)
  - [Commands](#commands)
  - [Arguments](#arguments)
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
| `--zoom` | no | Float, range **1.0–10.0** (default **2.0**) | Page render zoom |
| `--process_table` | no | Boolean string (default: `true`) | Process tables |

### `tag` only

| Option | Required | Type / expected value | Description |
|---|:---:|---|---|
| `--process_formula` | no | Boolean string (default: `true`) | Process formulas |

### Threshold options (`tag` / `template`)

Each value is clamped to **0.05–0.95**.

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
| `--name` | no | String (PDFix license); use for PDF → PDF without watermarks | PDFix license name |
| `--key` | no | String (PDFix license); use for PDF → PDF without watermarks | PDFix license key |

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

MathML from one formula image:

```bash
docker run --rm -v "$(pwd)":/data -w /data pdfix/pdf-accessibility-paddle:latest \
  mathml -i /data/formula.jpg -o /data/formula.xml
```

## Help & support

For PDFix SDK licensing or issues, contact `support@pdfix.net`.

## Licenses

- [PDFix Terms](https://pdfix.net/terms)
- [PaddleX](https://github.com/PaddlePaddle/PaddleX) — [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0)

