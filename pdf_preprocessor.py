"""
Structure-aware PDF preprocessor for OncoRAG.

Instead of treating a PDF as one long blob of text, this:
  1. Extracts text spans with font metadata (size, bold) using PyMuPDF
  2. Classifies each line as a HEADING or BODY line based on styling
  3. Groups body text under its nearest preceding heading -> "sections"
  4. Chunks each section's text (not the whole doc) with overlap,
     prepending the section title so every chunk carries its context

Output: a list of chunk dicts ready to embed, e.g.
  {
    "text": "Prevention: Cancer risk can be reduced by not using tobacco...",
    "section": "Prevention",
    "source": "who_cancer_factsheet.pdf",
    "page": 3,
    "chunk_id": "who_cancer_factsheet.pdf::Prevention::0"
  }
"""

import fitz  # PyMuPDF
import statistics
import re
from dataclasses import dataclass, field


@dataclass
class Line:
    text: str
    size: float
    bold: bool
    page: int


@dataclass
class Section:
    heading: str
    page: int
    body_lines: list = field(default_factory=list)


def extract_lines(pdf_path: str) -> list[Line]:
    """Pull every line of text out of the PDF along with its font size/weight."""
    doc = fitz.open(pdf_path)
    lines = []

    for page_num, page in enumerate(doc, start=1):
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                spans = line["spans"]
                if not spans:
                    continue
                # Merge spans on the same line into one string; use the
                # dominant (largest) span size/weight for classification
                text = "".join(s["text"] for s in spans).strip()
                if not text:
                    continue
                dominant = max(spans, key=lambda s: s["size"])
                is_bold = "bold" in dominant["font"].lower()
                lines.append(Line(text=text, size=dominant["size"], bold=is_bold, page=page_num))

    doc.close()
    return lines


def classify_headings(lines: list[Line]) -> list[Line]:
    """
    Determine the body font size (the mode) and flag lines that are
    GENUINELY larger as heading candidates.

    Important: bold-at-body-size is NOT enough on its own. Many documents
    (like WHO fact sheets) use bold *within* lists or sentences purely for
    emphasis -- e.g. "lung (2.6 million cases)" -- which would otherwise be
    misclassified as headings. Real section headings are visually set apart
    by size, so we require a meaningful size jump above body text.
    """
    sizes = [round(l.size, 1) for l in lines]
    body_size = statistics.mode(sizes) if sizes else 10.0
    size_threshold = body_size * 1.3  # require a real jump, not just +1pt

    candidates = []
    for line in lines:
        looks_like_heading = (
            line.size >= size_threshold
            and len(line.text.split()) <= 8
            and not line.text.strip().endswith((".", ",", ";"))
        )
        if looks_like_heading:
            candidates.append(line)

    # Second pass: de-duplicate "list runs". If 2+ heading candidates share
    # identical size/bold AND appear back-to-back in the line stream, they're
    # a bulleted list rendered in a consistent style -- not headings -- so
    # drop the whole run.
    filtered = []
    i = 0
    while i < len(candidates):
        run = [candidates[i]]
        j = i + 1
        while (j < len(candidates)
               and candidates[j].size == candidates[i].size
               and candidates[j].bold == candidates[i].bold
               and _is_adjacent_in_stream(lines, candidates[j - 1], candidates[j])):
            run.append(candidates[j])
            j += 1
        if len(run) == 1:
            filtered.append(run[0])
        # else: it's a list run, discard all of them as headings
        i = j
    return filtered


def _is_adjacent_in_stream(all_lines: list[Line], a: Line, b: Line, max_gap: int = 2) -> bool:
    """True if line b appears within max_gap lines after line a in the document."""
    try:
        ia = all_lines.index(a)
        ib = all_lines.index(b)
        return 0 < (ib - ia) <= max_gap
    except ValueError:
        return False


def group_into_sections(all_lines: list[Line], heading_lines: list[Line]) -> list[Section]:
    """Walk through lines in order, starting a new section at each heading."""
    heading_texts = {(h.text, h.page) for h in heading_lines}
    sections: list[Section] = []
    current = Section(heading="Introduction", page=all_lines[0].page if all_lines else 1)

    for line in all_lines:
        if (line.text, line.page) in heading_texts:
            if current.body_lines:  # don't keep empty leading sections
                sections.append(current)
            current = Section(heading=line.text, page=line.page)
        else:
            current.body_lines.append(line.text)

    if current.body_lines:
        sections.append(current)
    return sections


def chunk_sections(sections: list[Section], source_name: str,
                    chunk_size: int = 700, overlap: int = 100) -> list[dict]:
    """
    Chunk each section's body text independently (never spanning across
    section boundaries), prepending the heading to every chunk for context.
    """
    chunks = []
    for section in sections:
        full_text = " ".join(section.body_lines)
        full_text = re.sub(r"\s+", " ", full_text).strip()
        if not full_text:
            continue

        start = 0
        idx = 0
        while start < len(full_text):
            end = start + chunk_size
            piece = full_text[start:end]
            chunk_text = f"{section.heading}: {piece}"
            chunks.append({
                "text": chunk_text,
                "section": section.heading,
                "source": source_name,
                "page": section.page,
                "chunk_id": f"{source_name}::{section.heading}::{idx}",
            })
            start = end - overlap
            idx += 1
    return chunks


def preprocess_pdf(pdf_path: str, source_name: str | None = None) -> list[dict]:
    source_name = source_name or pdf_path.split("/")[-1]
    lines = extract_lines(pdf_path)
    headings = classify_headings(lines)
    sections = group_into_sections(lines, headings)
    return chunk_sections(sections, source_name)


if __name__ == "__main__":
    import sys, json

    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "cancer_fact_sheet.pdf"
    result = preprocess_pdf(pdf_path)

    print(f"Extracted {len(result)} chunks across "
          f"{len({c['section'] for c in result})} sections\n")
    for c in result[:3]:
        print(f"[{c['section']}] (page {c['page']})")
        print(c["text"][:200] + "...\n")

    with open("chunks_output.json", "w") as f:
        json.dump(result, f, indent=2)
