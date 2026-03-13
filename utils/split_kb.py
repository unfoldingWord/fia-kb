#!/usr/bin/env python3
"""
Split large markdown source files into chapter-level knowledge base files.
Handles 6 different dissertation/thesis formats with distinct heading patterns.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).parent
SRC = BASE / "markdown_source"
KB = BASE / "kb"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(text: str) -> str:
    """Convert text to a filename-safe slug."""
    text = text.lower()
    text = re.sub(r'[\\/:*?"<>|]', '', text)
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')


def write_md(path: Path, content: str, frontmatter: dict):
    """Write a markdown file with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_lines = ["---"]
    for k, v in frontmatter.items():
        if isinstance(v, str):
            fm_lines.append(f'{k}: "{v}"')
        else:
            fm_lines.append(f'{k}: {v}')
    fm_lines.append("---")
    fm_lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(fm_lines) + content)


def write_chapters(folder_name: str, chapters: list[tuple[str, str]], author: str, source: str):
    """Write a list of (title, content) chapter tuples to kb/<folder_name>/."""
    out_dir = KB / folder_name
    for i, (title, content) in enumerate(chapters):
        if not content.strip():
            continue
        if i == 0:
            fname = "00-front-matter.md"
        elif i == len(chapters) - 1 and any(kw in title.lower() for kw in
                ['bibliography', 'references', 'works cited', 'appendix']):
            fname = f"{i:02d}-{slugify(title)}.md"
        else:
            fname = f"{i:02d}-{slugify(title)}.md"
        fm = {
            "title": title.replace('"', '\\"'),
            "author": author,
            "source": source,
            "section": i,
        }
        write_md(out_dir / fname, content, fm)
    print(f"  -> {out_dir} ({len([c for c in chapters if c[1].strip()])} files)")


# ---------------------------------------------------------------------------
# Per-document splitters
# ---------------------------------------------------------------------------

def split_faith():
    """Faith Living Understanding - chapters marked as **Chapter N: Title** or # Chapter N:"""
    print("Processing: Faith Living Understanding")
    text = (SRC / "Faith Living Understanding.md").read_text(encoding="utf-8")
    lines = text.split("\n")

    # Identify chapter boundary lines.
    # Actual chapter content starts with lines like:
    #   5 **Chapter 1: Introduction**
    #   # Chapter 3: The Canon...
    # The TOC also has **Chapter N: lines but those have page numbers like "... 6**"
    # Content chapters: line starts with optional page-num, then **Chapter or # Chapter
    # We detect content chapters (not TOC) by: they DON'T have "...." in them

    chapter_pattern = re.compile(
        r'^(?:\d+\s+)?\*?\*?#?\s*Chapter\s+(\d+)\s*[\\:]+\s*(.+?)(?:\s*\.{3,}.*)?[\*]*$',
        re.IGNORECASE
    )
    bib_pattern = re.compile(r'^\*?\*?BIBLIOGRAPHY\*?\*?$', re.IGNORECASE)

    boundaries = []  # (line_idx, title)
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Skip TOC entries (contain dots like ".....")
        if '.....' in stripped:
            continue
        m = chapter_pattern.match(stripped)
        if m:
            num = m.group(1)
            title = m.group(2).strip().lstrip(':').strip().rstrip('*')
            boundaries.append((i, f"Chapter {num}: {title}"))
        elif bib_pattern.match(stripped):
            boundaries.append((i, "Bibliography"))

    chapters = []
    # Front matter is everything before first chapter
    if boundaries:
        front = "\n".join(lines[:boundaries[0][0]])
        chapters.append(("Front Matter", front))
        for j, (line_idx, title) in enumerate(boundaries):
            end = boundaries[j+1][0] if j+1 < len(boundaries) else len(lines)
            content = "\n".join(lines[line_idx:end])
            chapters.append((title, content))

    write_chapters("faith-living-understanding", chapters,
                   "Stephen Stringer", "Faith Living Understanding")


def split_kim():
    """Kim - chapters marked as # CHAPTER N: TITLE"""
    print("Processing: Kim Preaching as Discipling")
    fname = "kim_PREACHING AS DISCIPLING IN AN AUTHORITARIAN KOREAN CONTEXT- TOWARD A HERMENEUTICS OF HEARING.md"
    text = (SRC / fname).read_text(encoding="utf-8")
    lines = text.split("\n")

    # Match both # CHAPTER and **CHAPTER patterns
    chapter_pattern = re.compile(r'^(?:#|\*\*)\s*CHAPTER\s+(\d+)\s*[:\\]\s*(.+)', re.IGNORECASE)
    bib_pattern = re.compile(r'^#\s*Bibliography\s*$', re.IGNORECASE)

    boundaries = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Skip TOC entries (contain dots)
        if '.....' in stripped or '……' in stripped:
            continue
        m = chapter_pattern.match(stripped)
        if m:
            num = m.group(1)
            title_text = m.group(2).strip().lstrip(':').strip().rstrip('*')
            boundaries.append((i, f"Chapter {num}: {title_text}"))
            continue
        if bib_pattern.match(stripped):
            boundaries.append((i, "Bibliography"))

    chapters = []
    if boundaries:
        chapters.append(("Front Matter", "\n".join(lines[:boundaries[0][0]])))
        for j, (idx, title) in enumerate(boundaries):
            end = boundaries[j+1][0] if j+1 < len(boundaries) else len(lines)
            chapters.append((title, "\n".join(lines[idx:end])))

    write_chapters("kim-preaching-discipling", chapters,
                   "DaeJin Kim",
                   "Preaching as Discipling in an Authoritarian Korean Context")


def split_moon():
    """Moon - chapters marked as **Chapter N - Title** (sometimes with 'Reproduced...' prefix)"""
    print("Processing: Moon Using Proverbs")
    text = (SRC / "Moon_Using_proverbs_to_contextualiz.md").read_text(encoding="utf-8")
    lines = text.split("\n")

    # Pattern: **Chapter or plain Chapter + num - Title (with optional prefix text)
    chapter_pattern = re.compile(
        r'(?:\*\*)?Chapter\s+(\w+)\s*[-:]\s*(.+?)(?:\*\*)?(?:\d*)$',
        re.IGNORECASE
    )
    ref_pattern = re.compile(r'^#\s*References\s+Cited', re.IGNORECASE)

    boundaries = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Skip TOC entries (contain dots)
        if '.....' in stripped:
            continue
        # Skip lines in the TOC area (before line 250)
        if i < 250:
            continue
        m = chapter_pattern.search(stripped)
        if m:
            ch_num = m.group(1)
            title = m.group(2).strip().lstrip(':').strip().rstrip('*')
            # Skip in-paragraph references (line doesn't start with Chapter or prefix)
            if not (stripped.startswith('**Chapter') or stripped.startswith('Chapter')
                    or 'Reproduced with permission' in stripped):
                continue
            boundaries.append((i, f"Chapter {ch_num}: {title}"))
            continue
        if ref_pattern.match(stripped):
            boundaries.append((i, "References Cited"))

    chapters = []
    if boundaries:
        chapters.append(("Front Matter", "\n".join(lines[:boundaries[0][0]])))
        for j, (idx, title) in enumerate(boundaries):
            end = boundaries[j+1][0] if j+1 < len(boundaries) else len(lines)
            chapters.append((title, "\n".join(lines[idx:end])))

    write_chapters("moon-proverbs", chapters,
                   "W. Jay Moon",
                   "Using Proverbs to Contextualize Christianity in the Builsa Culture")


def split_madinger():
    """Madinger - chapters marked as **Chapter One/Two/etc: Title** with page-num prefix"""
    print("Processing: Madinger Transformative Learning")
    fname = "Madinger_TRANSFORMATIVE LEARNING THROUGH ORAL NARRATIVE IN A PARTICIPATORY.md"
    text = (SRC / fname).read_text(encoding="utf-8")
    lines = text.split("\n")

    chapter_pattern = re.compile(
        r'\*\*Chapter\s+(\w+)\s*[:\\]\s*(.+?)(?:\*\*)?$',
        re.IGNORECASE
    )
    # Also match the Prologue which is a # heading
    prologue_pattern = re.compile(r'^#\s+Prologue', re.IGNORECASE)
    appendix_pattern = re.compile(r'\*\*Appendix\s+1\*?\*?$', re.IGNORECASE)
    ref_pattern = re.compile(r'\*\*References\*\*$', re.IGNORECASE)

    boundaries = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if '.....' in stripped or '........' in stripped:
            continue
        if prologue_pattern.match(stripped) and not boundaries:
            boundaries.append((i, "Prologue and Chapter One: Introduction"))
            continue
        m = chapter_pattern.search(stripped)
        if m:
            ch_num = m.group(1)
            title = m.group(2).strip().lstrip(':').strip().rstrip('*')
            # Skip if this is in the TOC area (before line 400)
            if i < 400:
                continue
            # Chapter One is already captured with Prologue
            if ch_num.lower() == 'one':
                continue
            boundaries.append((i, f"Chapter {ch_num}: {title}"))
            continue
        if appendix_pattern.search(stripped) and i > 4000:
            boundaries.append((i, "Appendices"))
            continue
        if ref_pattern.search(stripped) and i > 4900:
            boundaries.append((i, "References"))

    chapters = []
    if boundaries:
        chapters.append(("Front Matter", "\n".join(lines[:boundaries[0][0]])))
        for j, (idx, title) in enumerate(boundaries):
            end = boundaries[j+1][0] if j+1 < len(boundaries) else len(lines)
            chapters.append((title, "\n".join(lines[idx:end])))

    write_chapters("madinger-transformative-learning", chapters,
                   "Charles Brent Madinger",
                   "Transformative Learning Through Oral Narrative")


def split_huisman():
    """Huisman - chapters marked inline as 'CHAPTER N' at end of paragraphs + WORKS CITED"""
    print("Processing: Huisman Beyond Orality")
    fname = "Huisman_Beyond orality and literacy reclaiming the sensorium for composition studies.md"
    text = (SRC / fname).read_text(encoding="utf-8")
    lines = text.split("\n")

    # Chapters appear at end of lines like: "...we are immersed. CHAPTER 1"
    # Also need to find ACKNOWLEDGEMENTS and WORKS CITED
    chapter_inline = re.compile(r'CHAPTER\s+(\d+)\s*$')
    works_cited = re.compile(r'^Works Cited', re.IGNORECASE)

    boundaries = []
    # ACKNOWLEDGEMENTS is the first real content section
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == '# ACKNOWLEDGEMENTS':
            boundaries.append((i, "Acknowledgements"))
            continue
        m = chapter_inline.search(stripped)
        if m and i > 100:  # Skip TOC references
            num = m.group(1)
            # Chapter titles from TOC
            ch_titles = {
                '1': "Walter Ong's Reception in English Studies",
                '2': "Speaking of Changes",
                '3': "Before Orality and Literacy",
                '4': "The (Not So) Great Divide: Recalling the Sensorium",
                '5': "Applications",
                '6': "Conclusion",
            }
            title = ch_titles.get(num, f"Chapter {num}")
            boundaries.append((i, f"Chapter {num}: {title}"))
            continue
        if works_cited.match(stripped) and i > 4000:
            boundaries.append((i, "Works Cited"))

    chapters = []
    if boundaries:
        chapters.append(("Front Matter", "\n".join(lines[:boundaries[0][0]])))
        for j, (idx, title) in enumerate(boundaries):
            end = boundaries[j+1][0] if j+1 < len(boundaries) else len(lines)
            chapters.append((title, "\n".join(lines[idx:end])))

    write_chapters("huisman-orality-literacy", chapters,
                   "Leo I. Huisman",
                   "Beyond Orality and Literacy: Reclaiming the Sensorium")


def convert_and_split_pickstock():
    """Convert pickstock PDF to text, then split by chapters."""
    print("Processing: Pickstock Dissertation (PDF conversion + split)")
    pdf_path = BASE / "pickstock dissertation.pdf"
    md_path = SRC / "pickstock dissertation.md"

    if not md_path.exists():
        print("  Converting PDF with pdftotext...")
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), str(md_path)],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"  ERROR: pdftotext failed: {result.stderr}")
            return
        print(f"  -> Wrote {md_path}")

    text = md_path.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")

    # Detect chapter patterns - word-form or numeric
    chapter_pattern = re.compile(
        r'^\s*Chapter\s+(One|Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|\d+|[IVXLC]+)\b\s*$',
        re.IGNORECASE
    )
    conclusion_pattern = re.compile(r'^\s*Conclusion\s*$', re.IGNORECASE)
    bib_pattern = re.compile(
        r'^\s*(BIBLIOGRAPHY|REFERENCES|WORKS CITED)\s*$', re.IGNORECASE
    )
    appendix_pattern = re.compile(
        r'^\s*(APPENDIX|Appendix)\s+([A-Z0-9])\b', re.IGNORECASE
    )

    boundaries = []
    # Find Introduction (standalone line, not in TOC)
    intro_pattern = re.compile(r'^Introduction\s*$', re.IGNORECASE)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # Skip TOC (lines with dots like ".....")
        if '.....' in stripped or '......' in stripped:
            continue
        if intro_pattern.match(stripped) and i > 100:
            boundaries.append((i, "Introduction"))
            continue
        m = chapter_pattern.match(stripped)
        if m and i > 100:  # Skip TOC references
            num = m.group(1)
            boundaries.append((i, f"Chapter {num}"))
            continue
        if conclusion_pattern.match(stripped) and i > 100:
            boundaries.append((i, "Conclusion"))
            continue
        if bib_pattern.match(stripped) and i > 100:
            boundaries.append((i, "Bibliography"))
            continue
        m2 = appendix_pattern.match(stripped)
        if m2 and i > 100 and len(stripped) < 80:
            boundaries.append((i, f"Appendix {m2.group(2)}"))

    if not boundaries:
        # Fallback: just write as single file
        print("  WARNING: No chapter boundaries found; writing as single file")
        out = KB / "pickstock-dissertation.md"
        write_md(out, text, {
            "title": "Pickstock Dissertation",
            "author": "Pickstock",
            "source": "pickstock dissertation.pdf",
            "section": 0,
        })
        return

    chapters = []
    chapters.append(("Front Matter", "\n".join(lines[:boundaries[0][0]])))
    for j, (idx, title) in enumerate(boundaries):
        end = boundaries[j+1][0] if j+1 < len(boundaries) else len(lines)
        chapters.append((title, "\n".join(lines[idx:end])))

    write_chapters("pickstock-dissertation", chapters,
                   "Pickstock", "Pickstock Dissertation")


# ---------------------------------------------------------------------------
# Small files: copy with frontmatter
# ---------------------------------------------------------------------------

SMALL_FILES = {
    "New Hope, A Theodramatic Approach to Trauma Healing.md": {
        "slug": "new-hope-trauma-healing.md",
        "author": "Stephen Stringer",
        "source": "New Hope: A Theodramatic Approach to Trauma Healing",
    },
    "Stringer. Widening the Table.md": {
        "slug": "stringer-widening-the-table.md",
        "author": "Stephen Stringer",
        "source": "Widening the Table",
    },
    "Reticular worldview.md": {
        "slug": "reticular-worldview.md",
        "author": "Unknown",
        "source": "Reticular Worldview",
    },
    "Eurasia Consultant meeting orality.md": {
        "slug": "eurasia-consultant-meeting.md",
        "author": "Unknown",
        "source": "Eurasia Consultant Meeting: Orality",
    },
    "SStringer 2025 BT conference presentation RD---practoce.md": {
        "slug": "sstringer-2025-bt-conference.md",
        "author": "Stephen Stringer",
        "source": "BT Conference 2025 Presentation",
    },
}


def copy_small_files():
    """Copy small files to kb/ with frontmatter."""
    print("Copying small files...")
    for src_name, info in SMALL_FILES.items():
        src_path = SRC / src_name
        if not src_path.exists():
            print(f"  WARNING: {src_name} not found, skipping")
            continue
        text = src_path.read_text(encoding="utf-8")
        # Extract title from first heading or first line
        title = info["source"]
        fm = {
            "title": title,
            "author": info["author"],
            "source": info["source"],
            "section": 0,
        }
        write_md(KB / info["slug"], text, fm)
        print(f"  -> {KB / info['slug']}")


# ---------------------------------------------------------------------------
# Index generation
# ---------------------------------------------------------------------------

def generate_index():
    """Generate kb/index.md with links to all documents."""
    print("Generating index.md...")
    lines = [
        "---",
        'title: "FIA Knowledge Base Index"',
        "---",
        "",
        "# FIA Knowledge Base",
        "",
    ]

    # Collect all directories and files
    dirs = sorted([d for d in KB.iterdir() if d.is_dir()])
    files = sorted([f for f in KB.iterdir() if f.is_file() and f.name != "index.md"])

    if dirs:
        lines.append("## Dissertations & Theses")
        lines.append("")
        for d in dirs:
            md_files = sorted(d.glob("*.md"))
            if not md_files:
                continue
            # Get source name from first file's frontmatter
            dir_title = d.name.replace("-", " ").title()
            lines.append(f"### {dir_title}")
            lines.append("")
            for f in md_files:
                rel = f.relative_to(KB)
                # Read title from frontmatter
                title = f.stem.replace("-", " ").title()
                try:
                    content = f.read_text(encoding="utf-8")
                    for line in content.split("\n"):
                        if line.startswith("title:"):
                            title = line.split(":", 1)[1].strip().strip('"')
                            break
                except:
                    pass
                lines.append(f"- [{title}]({rel.as_posix()})")
            lines.append("")

    if files:
        lines.append("## Papers & Articles")
        lines.append("")
        for f in files:
            rel = f.relative_to(KB)
            title = f.stem.replace("-", " ").title()
            try:
                content = f.read_text(encoding="utf-8")
                for line in content.split("\n"):
                    if line.startswith("title:"):
                        title = line.split(":", 1)[1].strip().strip('"')
                        break
            except:
                pass
            lines.append(f"- [{title}]({rel.as_posix()})")
        lines.append("")

    (KB / "index.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"  -> {KB / 'index.md'}")


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify():
    """Compare total line counts between source and output."""
    print("\n--- Verification ---")
    src_total = 0
    for f in SRC.glob("*.md"):
        src_total += len(f.read_text(encoding="utf-8", errors="replace").split("\n"))
    print(f"Source total lines: {src_total}")

    kb_total = 0
    kb_files = 0
    for f in KB.rglob("*.md"):
        content = f.read_text(encoding="utf-8")
        # Subtract frontmatter lines (between --- markers)
        in_fm = False
        fm_count = 0
        for line in content.split("\n"):
            if line.strip() == "---":
                fm_count += 1
                if fm_count == 2:
                    break
            elif fm_count >= 1:
                pass  # inside frontmatter
        # Count non-frontmatter lines
        all_lines = content.split("\n")
        # Find end of frontmatter
        fm_end = 0
        dashes = 0
        for i, line in enumerate(all_lines):
            if line.strip() == "---":
                dashes += 1
                if dashes == 2:
                    fm_end = i + 1
                    break
        content_lines = len(all_lines) - fm_end
        kb_total += content_lines
        kb_files += 1
    print(f"KB total content lines: {kb_total}")
    print(f"KB total files: {kb_files}")
    # Note: some lines may be added/removed due to blank line handling
    diff = abs(src_total - kb_total)
    pct = (diff / src_total * 100) if src_total else 0
    print(f"Difference: {diff} lines ({pct:.1f}%)")
    if pct > 5:
        print("WARNING: >5% difference - check for content loss!")
    else:
        print("OK: Content preserved within tolerance.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"Source: {SRC}")
    print(f"Output: {KB}")
    print()

    # Clean output directory
    if KB.exists():
        import shutil
        shutil.rmtree(KB)
    KB.mkdir(parents=True)

    # Step 1: Convert pickstock PDF
    convert_and_split_pickstock()
    print()

    # Step 2: Split large files
    split_faith()
    split_kim()
    split_moon()
    split_madinger()
    split_huisman()
    print()

    # Step 3: Copy small files
    copy_small_files()
    print()

    # Step 4: Generate index
    generate_index()
    print()

    # Step 5: Verify
    verify()


if __name__ == "__main__":
    main()
