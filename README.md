# ⚡ Bilingual Form Automation — GUI

A modern desktop automation tool that combines:

- 📄 PDF bilingual sentence extraction
- 🧠 Gale–Church statistical alignment
- 🌐 Google Form automation
- 🖥️ Dark-mode desktop GUI

The application extracts Uzbek and Turkmen text from PDFs, aligns sentence pairs intelligently, exports them into JSON, and automatically submits them into a Google Form using Playwright.

---

# ✨ Features

## 📑 PDF Text Extraction

Supports:

- Uzbek PDF extraction
- Turkmen PDF extraction
- Multi-page parsing
- Unicode normalization
- Mojibake repair
- OCR fallback support *(optional)*

Extraction methods:

1. Text blocks
2. Plain text
3. Word extraction
4. OCR *(if installed)*

---

## 🔗 Sentence Alignment Engine

Implements a customized Gale–Church alignment system with:

- Statistical sentence-length matching
- Merge handling (`1:2`, `2:1`, `2:2`)
- Fingerprint-based clean alignments
- Automatic mismatch skipping
- Alignment confidence tracking

### Supported Merge Types

| Type | Meaning |
|---|---|
| `1:1` | One sentence ↔ One sentence |
| `1:2` | One sentence ↔ Two sentences |
| `2:1` | Two sentences ↔ One sentence |
| `2:2` | Two sentences ↔ Two sentences |
| `1:0` | Deleted Uzbek sentence |
| `0:1` | Deleted Turkmen sentence |

---

## 🌐 Google Form Automation

Uses Playwright Chromium automation to:

- Open Google Forms
- Fill:
  - Student ID
  - Uzbek sentence
  - Turkmen sentence
- Submit automatically
- Detect confirmation responses
- Retry failed submissions
- Resume from saved progress

---

## 🖥️ GUI Interface

Built entirely with Tkinter.

Includes:

- Dark-themed interface
- Real-time console logs
- Progress bar
- File pickers
- Submission controls
- Stop button
- Progress reset system

---

# 🏗️ Architecture

```text
PDF Extraction
      ↓
Text Cleaning
      ↓
Sentence Splitting
      ↓
Gale-Church Alignment
      ↓
JSON Pair Export
      ↓
Playwright Automation
      ↓
Google Form Submission
```

---

# 📦 Installation

## 1. Clone Repository

```bash
git clone https://github.com/yourusername/bilingual-form-automation.git
cd bilingual-form-automation
```

---

## 2. Install Dependencies

```bash
pip install playwright pymupdf charset-normalizer ftfy pillow pytesseract
```

Optional fallback dependency:

```bash
pip install chardet
```

---

## 3. Install Chromium

```bash
playwright install chromium
```

---

# 📁 Project Structure

```text
project/
│
├── app.py
├── sent-pair.json
├── submission_progress.json
├── uzbek.pdf
├── turkmen.pdf
└── README.md
```

---

# 📚 Dependencies

| Package | Purpose |
|---|---|
| `playwright` | Browser automation |
| `pymupdf (fitz)` | PDF extraction |
| `charset-normalizer` | Encoding repair |
| `ftfy` | Mojibake cleanup |
| `pytesseract` | OCR support |
| `Pillow` | Image processing |
| `tkinter` | GUI |

---

# ⚙️ How It Works

# ① PDF Alignment

The application:

1. Loads Uzbek PDF
2. Loads Turkmen PDF
3. Extracts text from selected pages
4. Cleans malformed Unicode
5. Splits text into sentences
6. Runs Gale–Church alignment
7. Exports aligned pairs into JSON

### Example Output

```json
[
  {
    "uzbek": "Salom dunyo.",
    "turkmen": "Salam dünýä.",
    "_method": "fingerprint"
  }
]
```

---

# ② Form Submission

The automation system:

1. Loads generated JSON
2. Opens Google Form
3. Fills all fields
4. Clicks submit
5. Waits for confirmation
6. Saves progress index
7. Continues until completion

---

# 💾 Resume System

Progress is automatically saved into:

```text
submission_progress.json
```

If the application closes unexpectedly, submissions continue from the last successful index.

---

# 🔍 OCR Support

OCR activates only if:

- `pytesseract`
- `Pillow`

are installed.

Useful for:

- scanned PDFs
- image-based documents
- corrupted text extraction

---

# 🖥️ GUI Overview

## Left Panel

### PDF Alignment

- Uzbek PDF selector
- Turkmen PDF selector
- Start page
- End page
- Output JSON filename
- Run Alignment button

### Form Submission

- JSON selector
- Student ID
- Delay configuration
- Retry configuration
- Timeout configuration
- Headless mode toggle
- Run Submission button
- Stop button

---

## Right Panel

### Console

Displays:

- extraction logs
- alignment logs
- retry logs
- submission status
- errors
- ETA
- progress

---

# 🧠 Core Algorithms

# Gale–Church Alignment

Sentence alignment uses statistical sentence-length probability matching.

The alignment cost combines:

- merge penalties
- sentence length variance
- probability normalization

### Core Scoring Concept

```text
Cost = MergePenalty + LengthProbability
```

---

# 🔧 Unicode Repair Pipeline

The cleaning system handles:

- mojibake
- malformed apostrophes
- broken hyphenation
- hidden Unicode characters
- normalization issues

---

# 🧵 Threading Model

The GUI remains responsive using:

- Python threads
- independent asyncio event loops
- non-blocking Playwright execution

---

# 🛡️ Safety Features

## Retry Logic

Failed submissions retry automatically:

```python
for attempt in range(1, max_retries + 1):
```

---

## Graceful Stop

The stop button safely interrupts automation using:

```python
threading.Event()
```

---

## Validation Checks

The app validates:

- missing PDFs
- invalid JSON
- numeric settings
- missing Student ID
- missing browser dependencies

---

# 📜 Logging

The console displays:

- extraction progress
- page counts
- alignment statistics
- retry attempts
- ETA calculations
- completion reports

### Example

```text
[12/200] Processing…
✓ Confirmed
Avg: 2.1s | ETA: 6.5m
```

---

# 👻 Headless Mode

When enabled:

- browser runs invisibly
- faster execution
- lower resource usage

When disabled:

- browser window remains visible
- useful for debugging

---

# ⚡ Performance Notes

| Task | Speed |
|---|---|
| PDF extraction | ~1–3 sec/page |
| Alignment | ~1000+ sentences/sec |
| Form submission | ~2–5 sec/entry |

---

# 🚀 Potential Improvements

Possible future upgrades:

- Multi-language support
- CSV export
- AI semantic alignment
- Auto CAPTCHA handling
- Batch form support
- Parallel browser workers
- Drag-and-drop PDFs
- SQLite storage
- Cloud sync

---

# 🧯 Troubleshooting

## Playwright Not Installed

### Error

```text
❌ Playwright not installed
```

### Fix

```bash
pip install playwright
playwright install chromium
```

---

## PyMuPDF Missing

### Error

```text
❌ PyMuPDF (fitz) not installed
```

### Fix

```bash
pip install pymupdf
```

---

## OCR Not Working

Install:

```bash
pip install pytesseract pillow
```

Also install the Tesseract OCR engine separately.

---

# 📋 Example Workflow

```text
1. Select Uzbek PDF
2. Select Turkmen PDF
3. Choose page range
4. Run Alignment
5. Generate sent-pair.json
6. Enter Student ID
7. Run Submission
8. Watch automation complete automatically
```

---

# 📄 License

MIT License

---

# 👨‍💻 Author

Built for bilingual corpus alignment and automated linguistic data submission workflows.
