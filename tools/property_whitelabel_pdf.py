#!/usr/bin/env python3
"""Create customer-facing property PDFs from authorized source materials.

Current profile: cityhomes
- Rebrands the source header as ``univ合同会社``.
- Converts an ownership-style header into ``ご紹介...`` wording rather than
  claiming ownership by univ.
- Replaces the source's generic third-party restriction with a customer-facing
  univ introduction note when the business has confirmed distribution rights.
- Leaves property names, prices, yields, addresses, areas, structure, dates and
  other property facts unchanged.

The implementation intentionally uses PyMuPDF's built-in Japanese font plus
Helvetica for the Latin word "univ" so the output stays small and readable.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import fitz

CITYHOMES_FOOTER_OLD = "・本物件情報は貴社限りとし、他社への物件紹介はご遠慮ください。"
CITYHOMES_FOOTER_PREFIX = "・本資料は"
CITYHOMES_FOOTER_SUFFIX = "のご紹介資料です。最新状況はお問い合わせください。"


def _width(text: str, fontname: str, fontsize: float) -> float:
    return fitz.get_text_length(text, fontname=fontname, fontsize=fontsize)


def _insert_mixed(page: fitz.Page, x: float, baseline_y: float, parts: list[tuple[str, str]], fontsize: float) -> None:
    cursor = x
    for text, fontname in parts:
        page.insert_text(
            (cursor, baseline_y),
            text,
            fontsize=fontsize,
            fontname=fontname,
            color=(0, 0, 0),
            overlay=True,
        )
        cursor += _width(text, fontname, fontsize)


def _profile_cityhomes(page: fitz.Page, brand_latin: str, brand_jp: str) -> None:
    # Replace only the third footer bullet. Start the redaction inside the target
    # line so the immediately preceding bullet remains untouched.
    hits = page.search_for(CITYHOMES_FOOTER_OLD)
    if not hits:
        raise RuntimeError("Expected City Homes footer restriction was not found")

    for r in hits:
        page.add_redact_annot(
            fitz.Rect(r.x0 - 6, r.y0 + 2, min(page.rect.x1 - 10, r.x0 + 2100), r.y1 + 6),
            fill=(1, 1, 1),
        )
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

    for r in hits:
        _insert_mixed(
            page,
            r.x0,
            r.y0 + 31,
            [
                (CITYHOMES_FOOTER_PREFIX, "japan"),
                (brand_latin, "helv"),
                (brand_jp + CITYHOMES_FOOTER_SUFFIX, "japan"),
            ],
            28,
        )

    # City Homes uses two known one-page list layouts.
    if page.rect.width > 5000:  # sales/development list (approx 7003 x 4952)
        page.add_redact_annot(fitz.Rect(1160, 330, 1910, 486), fill=(1, 1, 1))
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_REMOVE)
        _insert_mixed(page, 1200, 445, [(brand_latin, "helv"), (brand_jp, "japan")], 64)
    else:  # residence list (approx 3968 x 2806)
        page.add_redact_annot(fitz.Rect(150, 270, 2480, 402), fill=(1, 1, 1))
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_REMOVE)
        _insert_mixed(
            page,
            200,
            375,
            [(brand_latin, "helv"), (brand_jp + "  ご紹介区分マンション", "japan")],
            56,
        )


def transform(input_pdf: Path, output_pdf: Path, profile: str, brand_latin: str, brand_jp: str) -> None:
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(input_pdf, output_pdf)
    doc = fitz.open(output_pdf)
    if doc.page_count != 1:
        doc.close()
        raise RuntimeError("Current profile expects a one-page property list PDF")

    page = doc[0]
    if profile == "cityhomes":
        _profile_cityhomes(page, brand_latin, brand_jp)
    else:
        doc.close()
        raise ValueError(f"Unsupported profile: {profile}")

    doc.saveIncr()
    doc.close()

    # Fail-closed QA on the edited PDF.
    check = fitz.open(output_pdf)
    text = check[0].get_text()
    check.close()
    if brand_latin not in text or brand_jp not in text:
        raise RuntimeError("Brand text missing after edit")
    if CITYHOMES_FOOTER_OLD in text:
        raise RuntimeError("Old third-party restriction still exists")
    if "株式会社シティホームズ" in text or "保有区分マンション" in text:
        raise RuntimeError("Old residence branding/ownership-style header still exists")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_pdf", type=Path)
    parser.add_argument("output_pdf", type=Path)
    parser.add_argument("--profile", default="cityhomes")
    parser.add_argument("--brand-latin", default="univ")
    parser.add_argument("--brand-jp", default="合同会社")
    args = parser.parse_args()
    transform(args.input_pdf, args.output_pdf, args.profile, args.brand_latin, args.brand_jp)


if __name__ == "__main__":
    main()
