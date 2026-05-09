# ⚡ Bilingual Form Automation GUI

A high-performance desktop application designed to bridge the gap between bilingual PDF documents and Google Forms. This tool automates the extraction, alignment, and submission of parallel texts (Uzbek/Turkmen) into a structured web form.

## 🚀 Features

* **PDF Alignment (Gale-Church Algorithm):** Uses a probabilistic model to accurately align sentences between two different PDF versions of a document.
* **Intelligent Text Extraction:** Powered by `PyMuPDF` with built-in mojibake (encoding error) repair via `ftfy` and `charset-normalizer`.
* **Playwright Automation:** Automates the Chromium browser to fill and submit Google Forms with high reliability and retry logic.
* **Modern Dark-Mode GUI:** A sleek `tkinter` interface featuring real-time console logging and a progress bar.
* **Resumable Sessions:** Progress is automatically saved to `submission_progress.json`, allowing you to pause and resume work without duplicates.

---

## 🛠 Installation

### 1. Prerequisites
Ensure you have **Python 3.8+** installed on your system.

### 2. Install Dependencies
Run the following command to install the required libraries:
```bash
pip install playwright pymupdf charset-normalizer ftfy
