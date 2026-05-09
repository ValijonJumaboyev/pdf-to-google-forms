"""
BILINGUAL FORM AUTOMATION — GUI
=================================
Combines PDF alignment (manual.py) + Google Form submission (form_automation.py)
into a single desktop application.

Dependencies:
    pip install playwright pymupdf charset-normalizer ftfy
    playwright install chromium
"""

import json
import os
import re
import math
import asyncio
import logging
import unicodedata
import threading
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Literal

# ─────────────────────────────────────────────────────────────────────────────
# OPTIONAL DEPENDENCY IMPORTS
# ─────────────────────────────────────────────────────────────────────────────
try:
    import fitz
    _FITZ = True
except ImportError:
    _FITZ = False

try:
    from charset_normalizer import from_bytes
    _CHARSET_NORMALIZER = True
except ImportError:
    try:
        import chardet
        _CHARSET_NORMALIZER = False
    except ImportError:
        chardet = None
        _CHARSET_NORMALIZER = False

try:
    import ftfy
    _FTFY_AVAILABLE = True
except ImportError:
    _FTFY_AVAILABLE = False

try:
    import pytesseract
    from PIL import Image
    import io
    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# ALIGNMENT LOGIC (from manual.py)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AlignedPair:
    uzbek:    str
    turkmen:  str
    method:   str = "fingerprint"
    uz_idx:   int = -1
    turk_idx: int = -1

    def to_dict(self):
        return {"uzbek": self.uzbek, "turkmen": self.turkmen, "_method": self.method}


@dataclass
class AlignmentStats:
    total:               int = 0
    fingerprint:         int = 0
    fallback:            int = 0
    fallback_suspicious: int = 0
    skipped_uz:          int = 0
    skipped_turk:        int = 0

    def report(self):
        pct_11 = 100 * self.fingerprint / self.total if self.total else 0
        pct_mx = 100 * self.fallback    / self.total if self.total else 0
        return (
            f"\n{'='*54}\n"
            f"  Total pairs output     : {self.total}\n"
            f"  Clean 1:1 alignments   : {self.fingerprint} ({pct_11:.1f}%)\n"
            f"  Merged blocks (1:2 etc): {self.fallback}  ({pct_mx:.1f}%)\n"
            f"  Deleted UZ (no match)  : {self.skipped_uz}\n"
            f"  Deleted TURK (no match): {self.skipped_turk}\n"
            f"{'='*54}"
        )


MergeType = Literal["1:1", "1:2", "2:1", "1:0", "0:1", "2:2"]
MERGE_COSTS: dict = {"1:1": 0.0, "1:2": 0.8, "2:1": 0.8, "1:0": 2.5, "0:1": 2.5, "2:2": 1.2}
_MEAN, _VAR = 1.0, 6.8


def _length_prob(uz_chars, turk_chars):
    if uz_chars == 0 and turk_chars == 0: return 0.0
    if uz_chars == 0 or turk_chars == 0:  return 3.0
    delta = (turk_chars - uz_chars * _MEAN) / math.sqrt(uz_chars * _VAR)
    z = abs(delta)
    if z < 0.5: return 0.1
    if z < 1.0: return 0.4
    if z < 1.5: return 0.9
    if z < 2.0: return 1.6
    if z < 2.5: return 2.5
    return 3.5


def _cell_cost(uz_block, turk_block, merge):
    return MERGE_COSTS[merge] + _length_prob(
        sum(len(s) for s in uz_block),
        sum(len(s) for s in turk_block)
    )


def gale_church_align(uz_sents, turk_sents):
    m, n = len(uz_sents), len(turk_sents)
    INF   = float("inf")
    cost  = [[INF] * (n + 1) for _ in range(m + 1)]
    trace = [[None] * (n + 1) for _ in range(m + 1)]
    cost[0][0] = 0.0

    MOVES = [(1,1,"1:1"),(1,2,"1:2"),(2,1,"2:1"),(1,0,"1:0"),(0,1,"0:1"),(2,2,"2:2")]

    for i in range(m + 1):
        for j in range(n + 1):
            if i == 0 and j == 0:
                continue
            best_cost, best_move = INF, None
            for di, dj, mtype in MOVES:
                pi, pj = i - di, j - dj
                if pi < 0 or pj < 0:
                    continue
                prev = cost[pi][pj]
                if prev == INF:
                    continue
                c = prev + _cell_cost(
                    uz_sents[pi:i],
                    turk_sents[pj:j],
                    mtype
                )
                if c < best_cost:
                    best_cost, best_move = c, (di, dj, mtype)
            cost[i][j]  = best_cost
            trace[i][j] = best_move

    path, i, j = [], m, n
    while i > 0 or j > 0:
        move = trace[i][j]
        if move is None:
            break
        di, dj, mtype = move
        path.append((i - di, i, j - dj, j, mtype))
        i -= di; j -= dj
    path.reverse()

    stats = AlignmentStats()
    pairs: list[AlignedPair] = []
    for uz_s, uz_e, turk_s, turk_e, mtype in path:
        uz_block   = uz_sents[uz_s:uz_e]
        turk_block = turk_sents[turk_s:turk_e]
        if mtype == "1:0":
            stats.skipped_uz += 1; continue
        if mtype == "0:1":
            stats.skipped_turk += 1; continue
        uz_text   = " ".join(uz_block)
        turk_text = " ".join(turk_block)
        method    = "fingerprint" if mtype == "1:1" else "gale_church"
        if mtype == "1:1":
            stats.fingerprint += 1
        else:
            stats.fallback += 1
        pairs.append(AlignedPair(
            uzbek=uz_text, turkmen=turk_text, method=method,
            uz_idx=uz_s, turk_idx=turk_s
        ))
        stats.total += 1
    return pairs, stats


_PUA_RE = re.compile(r"[\uE000-\uF8FF]")
_WORD_CHAR = r"[A-Za-z\u0400-\u04FF\u00C0-\u024F\u02BB\u02BC]"
_ABBR_RE   = re.compile(r"\b([A-ZÜÖŞŽÄÝ])\.")


def clean_text(text):
    text = _PUA_RE.sub("", text)
    text = re.sub(r"(\w+)-\s+(\w)", r"\1\2", text)
    text = text.replace("\xad", "").replace("\u200c", "").replace("\ufeff", "")
    text = text.replace("\u2019", "\u02BC").replace("`", "\u02BC").replace("'", "\u02BC")
    text = re.sub(rf"(\d)({_WORD_CHAR})", r"\1 \2", text)
    text = re.sub(rf"(\w{{3,}})([.!?])({_WORD_CHAR})", r"\1\2 \3", text)
    return " ".join(text.split())


_ABBREVS = {"dr","mr","mrs","ms","prof","sr","jr","vs","etc","fig","vol","no","pp","ed","ж","б","м","б-н","ш-дагы"}
_SENT_SPLIT_RE    = re.compile(r"(?<=[.!?])\s+")
_NUMBERED_ITEM_RE = re.compile(r"^\d{1,3}\.$")


def split_sentences(text, min_len=15):
    raw_parts = _SENT_SPLIT_RE.split(text)
    sentences = []
    i = 0
    while i < len(raw_parts):
        part = raw_parts[i].strip()
        if part:
            last_token = part.rsplit(None, 1)[-1].rstrip(".")
            if last_token.lower() in _ABBREVS and i + 1 < len(raw_parts):
                sentences.append(part + " " + raw_parts[i + 1].strip())
                i += 2
                continue
        sentences.append(part)
        i += 1
    return [s for s in sentences if s and len(s) >= min_len and not _NUMBERED_ITEM_RE.match(s)]


def _looks_like_mojibake(text):
    if not text: return False
    latin_ext = sum(1 for c in text if "\u00C0" <= c <= "\u00FF")
    if len(text) > 4 and latin_ext / len(text) > 0.15: return True
    return "Ã" in text or "â€" in text


def _attempt_recode(text, page_num):
    candidates = [text]
    for enc_from, enc_to in [("latin-1","cp1252"),("latin-1","utf-8")]:
        try:
            candidates.append(text.encode(enc_from).decode(enc_to))
        except Exception:
            pass
    def density(s): return sum(1 for c in s if "\u00C0" <= c <= "\u00FF") / max(len(s),1)
    return min(candidates, key=density)


def extract_page_text(page, page_num, cfg_encoding, log_fn):
    min_chars = cfg_encoding.get("min_text_per_page", 20)

    # Method 1: blocks
    try:
        blocks = page.get_text("blocks")
        lines  = [b[4].strip() for b in blocks if b[6] == 0 and b[4].strip()]
        result = "\n".join(lines)
        if _looks_like_mojibake(result):
            result = _attempt_recode(result, page_num)
        if _FTFY_AVAILABLE and cfg_encoding.get("mojibake_repair"):
            result = ftfy.fix_text(result)
        result = unicodedata.normalize("NFKC", result)
        if len(result.strip()) >= min_chars:
            return result
    except Exception:
        pass

    # Method 2: plain text
    try:
        result = page.get_text("text")
        if len(result.strip()) >= min_chars:
            return result
    except Exception:
        pass

    # Method 3: words
    try:
        words = page.get_text("words")
        if words:
            return " ".join(w[4] for w in words)
    except Exception:
        pass

    return ""


def extract_pages(pdf_path, start_page, end_page, log_fn=print):
    if not _FITZ:
        log_fn("❌ PyMuPDF (fitz) not installed. Run: pip install pymupdf")
        return ""
    cfg_enc = {"mojibake_repair": True, "min_text_per_page": 20}
    doc = fitz.open(pdf_path)
    texts = []
    for pn in range(start_page, min(end_page, len(doc))):
        page = doc[pn]
        t    = extract_page_text(page, pn, cfg_enc, log_fn)
        texts.append(clean_text(t))
        log_fn(f"  📄 Page {pn+1} extracted ({len(t)} chars)")
    doc.close()
    return "\n".join(texts)


def run_alignment(uz_pdf, turk_pdf, start_page, end_page, output_json, log_fn):
    log_fn("📖 Extracting Uzbek PDF…")
    uz_text   = extract_pages(uz_pdf,   start_page, end_page, log_fn)
    log_fn("📖 Extracting Turkmen PDF…")
    turk_text = extract_pages(turk_pdf, start_page, end_page, log_fn)

    uz_sents   = split_sentences(uz_text)
    turk_sents = split_sentences(turk_text)
    log_fn(f"📝 Sentences — UZ: {len(uz_sents)}  TURK: {len(turk_sents)}")

    log_fn("🔗 Running Gale-Church alignment…")
    pairs, stats = gale_church_align(uz_sents, turk_sents)
    log_fn(stats.report())

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump([p.to_dict() for p in pairs], f, ensure_ascii=False, indent=2)
    log_fn(f"✅ Saved {len(pairs)} pairs → {output_json}")
    return len(pairs)


# ─────────────────────────────────────────────────────────────────────────────
# FORM SUBMISSION LOGIC (from form_automation.py)
# ─────────────────────────────────────────────────────────────────────────────

FORM_URL           = "https://forms.gle/PvcKF6WPFLMtpddq7"
CONFIRMATION_REGEX = r"(response has been recorded|javobingiz qabul qilindi|ответ записан|jogabyňyz hasaba alyndy|your response)"
PROGRESS_FILE      = "submission_progress.json"


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("last_completed_index", -1)
        except Exception:
            pass
    return -1


def save_progress(index):
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_completed_index": index}, f)


async def fill_and_submit(page, student_id, uzbek, turkmen, timeout, log_fn):
    try:
        from playwright.async_api import expect
        await page.goto(FORM_URL, wait_until="networkidle")
        fields = page.locator("input[type='text'], textarea")
        if await fields.count() < 3:
            log_fn(f"  ⚠ Expected 3 fields, found {await fields.count()}")
            return False
        await fields.nth(0).fill(student_id)
        await fields.nth(1).fill(uzbek)
        await fields.nth(2).fill(turkmen)

        submit_btn = page.locator(
            'div[role="button"][jsname="M2UYVd"], '
            'div[role="button"]:has-text("Submit"), '
            'div[role="button"]:has-text("Yuborish")'
        ).first
        await submit_btn.click()

        content = await page.content()
        return bool(re.search(CONFIRMATION_REGEX, content, re.IGNORECASE))
    except Exception as e:
        log_fn(f"  ⚠ Error: {str(e)[:120]}")
        return False


async def run_submission_async(json_file, student_id, delay, max_retries, timeout,
                                headless, log_fn, progress_cb, stop_event):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        log_fn("❌ Playwright not installed. Run: pip install playwright && playwright install chromium")
        return

    if not os.path.exists(json_file):
        log_fn(f"❌ File not found: {json_file}")
        return

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    last_idx  = load_progress()
    start_idx = last_idx + 1

    if start_idx >= len(data):
        log_fn("✅ All tasks already completed.")
        return

    log_fn(f"▶ Resuming from #{start_idx + 1} / {len(data)}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        page.set_default_timeout(timeout)

        successful = 0
        start_time = datetime.now()

        try:
            for i in range(start_idx, len(data)):
                if stop_event.is_set():
                    log_fn("⏹ Stopped by user.")
                    break

                uz = data[i].get("uzbek", "").strip()
                tk_text = data[i].get("turkmen", "").strip()
                log_fn(f"[{i+1}/{len(data)}] Processing…")

                success = False
                for attempt in range(1, max_retries + 1):
                    if await fill_and_submit(page, student_id, uz, tk_text, timeout, log_fn):
                        success = True
                        break
                    log_fn(f"  ↺ Retry {attempt}/{max_retries}…")
                    await asyncio.sleep(2)

                if success:
                    successful += 1
                    save_progress(i)
                    log_fn("  ✓ Confirmed")
                else:
                    log_fn("  ✗ Failed permanently")

                elapsed = (datetime.now() - start_time).total_seconds()
                avg     = elapsed / (i - start_idx + 1)
                eta     = avg * (len(data) - (i + 1)) / 60
                log_fn(f"  Avg: {avg:.1f}s | ETA: {eta:.1f}m")
                progress_cb(i + 1, len(data))
                await asyncio.sleep(delay)

        except Exception as e:
            log_fn(f"⚠ Unexpected error: {e}")
        finally:
            await browser.close()
            log_fn(f"\n🏁 Done. Successful: {successful} / {len(data) - start_idx}")


# ─────────────────────────────────────────────────────────────────────────────
# GUI
# ─────────────────────────────────────────────────────────────────────────────

DARK_BG    = "#0f1117"
PANEL_BG   = "#1a1d27"
ACCENT     = "#4f8ef7"
ACCENT2    = "#7c3aed"
SUCCESS    = "#22c55e"
WARNING    = "#f59e0b"
DANGER     = "#ef4444"
TEXT_MAIN  = "#e2e8f0"
TEXT_DIM   = "#64748b"
BORDER     = "#2d3148"
FONT_MONO  = ("Consolas", 10)
FONT_BODY  = ("Segoe UI", 10)
FONT_BOLD  = ("Segoe UI Semibold", 10)
FONT_H1    = ("Segoe UI Semibold", 14)
FONT_H2    = ("Segoe UI Semibold", 11)


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Bilingual Form Automation")
        self.geometry("900x680")
        self.minsize(760, 580)
        self.configure(bg=DARK_BG)
        self._stop_event = threading.Event()
        self._build_ui()

    # ── UI CONSTRUCTION ──────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=PANEL_BG, height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="⚡ Bilingual Form Automation",
                 font=FONT_H1, bg=PANEL_BG, fg=TEXT_MAIN).pack(side="left", padx=20, pady=14)
        tk.Label(hdr, text="PDF align → Google Form submit",
                 font=FONT_BODY, bg=PANEL_BG, fg=TEXT_DIM).pack(side="left")

        # Separator
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # Main body
        body = tk.Frame(self, bg=DARK_BG)
        body.pack(fill="both", expand=True, padx=16, pady=12)

        # Left panel
        left = tk.Frame(body, bg=DARK_BG, width=330)
        left.pack(side="left", fill="y", padx=(0,10))
        left.pack_propagate(False)

        self._build_config_panel(left)

        # Right panel (log)
        right = tk.Frame(body, bg=DARK_BG)
        right.pack(side="left", fill="both", expand=True)
        self._build_log_panel(right)

    def _section(self, parent, title):
        tk.Label(parent, text=title, font=FONT_H2,
                 bg=DARK_BG, fg=ACCENT).pack(anchor="w", pady=(14,4))
        frm = tk.Frame(parent, bg=PANEL_BG, bd=0,
                       highlightbackground=BORDER, highlightthickness=1)
        frm.pack(fill="x")
        return frm

    def _row(self, parent, label, widget_builder):
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill="x", padx=12, pady=5)
        tk.Label(row, text=label, font=FONT_BODY,
                 bg=PANEL_BG, fg=TEXT_DIM, width=13, anchor="w").pack(side="left")
        w = widget_builder(row)
        w.pack(side="left", fill="x", expand=True)
        return w

    def _entry(self, parent, textvariable, **kw):
        return tk.Entry(parent, textvariable=textvariable,
                        bg="#252840", fg=TEXT_MAIN, insertbackground=TEXT_MAIN,
                        relief="flat", font=FONT_BODY,
                        highlightbackground=BORDER, highlightthickness=1, **kw)

    def _file_row(self, parent, label, var):
        row = tk.Frame(parent, bg=PANEL_BG)
        row.pack(fill="x", padx=12, pady=5)
        tk.Label(row, text=label, font=FONT_BODY,
                 bg=PANEL_BG, fg=TEXT_DIM, width=13, anchor="w").pack(side="left")
        ent = tk.Entry(row, textvariable=var, bg="#252840", fg=TEXT_MAIN,
                       insertbackground=TEXT_MAIN, relief="flat", font=FONT_BODY,
                       highlightbackground=BORDER, highlightthickness=1)
        ent.pack(side="left", fill="x", expand=True)
        tk.Button(row, text="…", bg=ACCENT, fg="white", relief="flat",
                  font=FONT_BOLD, padx=6, cursor="hand2",
                  command=lambda: self._pick_file(var)).pack(side="left", padx=(4,0))

    def _build_config_panel(self, parent):
        # ── STEP 1: PDF Alignment
        f1 = self._section(parent, "① PDF Alignment")
        pad = tk.Frame(f1, bg=PANEL_BG)
        pad.pack(fill="x", pady=4)

        self._uzpdf_var   = tk.StringVar()
        self._turkpdf_var = tk.StringVar()
        self._outjson_var = tk.StringVar(value="sent-pair.json")
        self._start_var   = tk.StringVar(value="121")
        self._end_var     = tk.StringVar(value="156")

        self._file_row(f1, "Uzbek PDF",   self._uzpdf_var)
        self._file_row(f1, "Turkmen PDF", self._turkpdf_var)

        rng = tk.Frame(f1, bg=PANEL_BG)
        rng.pack(fill="x", padx=12, pady=5)
        tk.Label(rng, text="Pages", font=FONT_BODY, bg=PANEL_BG, fg=TEXT_DIM,
                 width=13, anchor="w").pack(side="left")
        tk.Label(rng, text="Start:", font=FONT_BODY, bg=PANEL_BG,
                 fg=TEXT_DIM).pack(side="left")
        tk.Entry(rng, textvariable=self._start_var, width=6, bg="#252840",
                 fg=TEXT_MAIN, insertbackground=TEXT_MAIN, relief="flat",
                 font=FONT_BODY).pack(side="left", padx=3)
        tk.Label(rng, text="End:", font=FONT_BODY, bg=PANEL_BG,
                 fg=TEXT_DIM).pack(side="left")
        tk.Entry(rng, textvariable=self._end_var, width=6, bg="#252840",
                 fg=TEXT_MAIN, insertbackground=TEXT_MAIN, relief="flat",
                 font=FONT_BODY).pack(side="left", padx=3)

        row = tk.Frame(f1, bg=PANEL_BG)
        row.pack(fill="x", padx=12, pady=5)
        tk.Label(row, text="Output JSON", font=FONT_BODY, bg=PANEL_BG,
                 fg=TEXT_DIM, width=13, anchor="w").pack(side="left")
        tk.Entry(row, textvariable=self._outjson_var, bg="#252840", fg=TEXT_MAIN,
                 insertbackground=TEXT_MAIN, relief="flat", font=FONT_BODY).pack(
                     side="left", fill="x", expand=True)

        tk.Frame(f1, bg=PANEL_BG, height=6).pack()
        self._align_btn = tk.Button(f1, text="▶  Run Alignment", font=FONT_BOLD,
                                    bg=ACCENT2, fg="white", relief="flat",
                                    activebackground="#6d28d9", cursor="hand2",
                                    pady=7, command=self._start_alignment)
        self._align_btn.pack(fill="x", padx=12, pady=(0,10))

        # ── STEP 2: Form Submission
        f2 = self._section(parent, "② Form Submission")

        self._id_var       = tk.StringVar(value="28")
        self._delay_var    = tk.StringVar(value="2")
        self._retries_var  = tk.StringVar(value="1")
        self._timeout_var  = tk.StringVar(value="15")
        self._headless_var = tk.BooleanVar(value=False)
        self._json_var     = tk.StringVar(value="sent-pair.json")

        self._file_row(f2, "Pairs JSON", self._json_var)

        for lbl, var in [("Student ID", self._id_var),
                          ("Delay (s)",  self._delay_var),
                          ("Retries",    self._retries_var),
                          ("Timeout (s)",self._timeout_var)]:
            self._row(f2, lbl, lambda p, v=var: self._entry(p, v))

        chk_row = tk.Frame(f2, bg=PANEL_BG)
        chk_row.pack(fill="x", padx=12, pady=5)
        tk.Checkbutton(chk_row, text="Headless (no browser window)",
                       variable=self._headless_var, bg=PANEL_BG, fg=TEXT_MAIN,
                       activebackground=PANEL_BG, selectcolor="#252840",
                       font=FONT_BODY).pack(side="left")

        tk.Frame(f2, bg=PANEL_BG, height=2).pack()

        btn_row = tk.Frame(f2, bg=PANEL_BG)
        btn_row.pack(fill="x", padx=12, pady=(0,10))
        self._submit_btn = tk.Button(btn_row, text="▶  Run Submission", font=FONT_BOLD,
                                     bg=SUCCESS, fg="white", relief="flat",
                                     activebackground="#16a34a", cursor="hand2",
                                     pady=7, command=self._start_submission)
        self._submit_btn.pack(side="left", fill="x", expand=True)
        self._stop_btn = tk.Button(btn_row, text="⏹", font=FONT_BOLD,
                                   bg=DANGER, fg="white", relief="flat",
                                   activebackground="#dc2626", cursor="hand2",
                                   pady=7, width=4, command=self._stop)
        self._stop_btn.pack(side="left", padx=(6,0))

        # Reset progress
        tk.Button(f2, text="🗑  Reset Submission Progress", font=FONT_BODY,
                  bg=PANEL_BG, fg=WARNING, relief="flat", cursor="hand2",
                  pady=3, command=self._reset_progress).pack(padx=12, pady=(0,8))

    def _build_log_panel(self, parent):
        tk.Label(parent, text="Console", font=FONT_H2,
                 bg=DARK_BG, fg=ACCENT).pack(anchor="w", pady=(14,4))

        self._log = scrolledtext.ScrolledText(
            parent, bg="#0d0f1a", fg="#a3e635", insertbackground=TEXT_MAIN,
            font=FONT_MONO, relief="flat", wrap="word",
            highlightbackground=BORDER, highlightthickness=1
        )
        self._log.pack(fill="both", expand=True)
        self._log.config(state="disabled")

        # Progress bar
        pb_frame = tk.Frame(parent, bg=DARK_BG)
        pb_frame.pack(fill="x", pady=(6,0))
        self._progress_label = tk.Label(pb_frame, text="Ready", font=FONT_BODY,
                                        bg=DARK_BG, fg=TEXT_DIM)
        self._progress_label.pack(anchor="w")

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Dark.Horizontal.TProgressbar",
                        troughcolor=PANEL_BG, background=ACCENT,
                        thickness=6)
        self._pb = ttk.Progressbar(pb_frame, style="Dark.Horizontal.TProgressbar",
                                   mode="determinate")
        self._pb.pack(fill="x", pady=(2,0))

        # Clear button
        tk.Button(parent, text="Clear log", font=("Segoe UI", 9),
                  bg=PANEL_BG, fg=TEXT_DIM, relief="flat", cursor="hand2",
                  command=self._clear_log).pack(anchor="e", pady=(4,0))

    # ── HELPERS ──────────────────────────────────────────────────────────────

    def _pick_file(self, var):
        path = filedialog.askopenfilename(
            filetypes=[("PDF files","*.pdf"), ("JSON files","*.json"), ("All","*.*")]
        )
        if path:
            var.set(path)

    def _log_write(self, msg):
        self._log.config(state="normal")
        self._log.insert("end", msg + "\n")
        self._log.see("end")
        self._log.config(state="disabled")

    def _clear_log(self):
        self._log.config(state="normal")
        self._log.delete("1.0", "end")
        self._log.config(state="disabled")

    def _set_progress(self, current, total):
        pct = int(100 * current / total) if total else 0
        self._pb["value"] = pct
        self._progress_label.config(text=f"Progress: {current} / {total}  ({pct}%)")

    def _reset_progress(self):
        if os.path.exists(PROGRESS_FILE):
            os.remove(PROGRESS_FILE)
            self._log_write("🗑 Progress file removed — will restart from index 0.")
        else:
            self._log_write("ℹ No progress file found.")

    def _stop(self):
        self._stop_event.set()
        self._log_write("⏹ Stop requested…")

    # ── ALIGNMENT ────────────────────────────────────────────────────────────

    def _start_alignment(self):
        uz   = self._uzpdf_var.get().strip()
        turk = self._turkpdf_var.get().strip()
        out  = self._outjson_var.get().strip()

        if not uz or not os.path.exists(uz):
            messagebox.showerror("Missing file", "Please select the Uzbek PDF.")
            return
        if not turk or not os.path.exists(turk):
            messagebox.showerror("Missing file", "Please select the Turkmen PDF.")
            return

        try:
            start = int(self._start_var.get()) - 1  # 0-indexed
            end   = int(self._end_var.get())
        except ValueError:
            messagebox.showerror("Invalid", "Page numbers must be integers.")
            return

        self._align_btn.config(state="disabled")
        self._log_write("\n" + "─"*50)
        self._log_write(f"🚀 Starting alignment  [{datetime.now().strftime('%H:%M:%S')}]")

        def worker():
            try:
                count = run_alignment(uz, turk, start, end, out, self._log_write)
                self._json_var.set(out)
                self._log_write(f"✅ Alignment complete — {count} pairs.")
            except Exception as e:
                self._log_write(f"❌ Alignment error: {e}")
            finally:
                self.after(0, lambda: self._align_btn.config(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

    # ── SUBMISSION ───────────────────────────────────────────────────────────

    def _start_submission(self):
        json_file  = self._json_var.get().strip()
        student_id = self._id_var.get().strip()

        if not json_file or not os.path.exists(json_file):
            messagebox.showerror("Missing file", "Please select a valid pairs JSON file.")
            return
        if not student_id:
            messagebox.showerror("Missing", "Please enter your Student ID.")
            return

        try:
            delay    = float(self._delay_var.get())
            retries  = int(self._retries_var.get())
            timeout  = int(self._timeout_var.get()) * 1000
        except ValueError:
            messagebox.showerror("Invalid", "Delay / Retries / Timeout must be numbers.")
            return

        headless = self._headless_var.get()
        self._stop_event.clear()
        self._submit_btn.config(state="disabled")
        self._log_write("\n" + "─"*50)
        self._log_write(f"🚀 Starting submission  [{datetime.now().strftime('%H:%M:%S')}]")
        self._log_write(f"   ID={student_id}  delay={delay}s  retries={retries}  headless={headless}")

        def worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(
                    run_submission_async(
                        json_file, student_id, delay, retries, timeout,
                        headless, self._log_write,
                        lambda c, t: self.after(0, lambda: self._set_progress(c, t)),
                        self._stop_event
                    )
                )
            finally:
                loop.close()
                self.after(0, lambda: self._submit_btn.config(state="normal"))

        threading.Thread(target=worker, daemon=True).start()


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()