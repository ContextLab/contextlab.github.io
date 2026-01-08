#!/usr/bin/env python3
"""Onboard new lab members.

This script:
1. Processes photo with hand-drawn border (if provided)
2. Generates or edits bio using local LLM (gpt-oss-20b)
3. Adds member to people.xlsx
4. Adds member to JRM_CV.tex
5. Rebuilds people.html

Idempotent: Running twice with same name will update existing entry.

Usage:
    python onboard_member.py "First Last"
    python onboard_member.py "First Last" --rank "grad student"
    python onboard_member.py "First Last" --photo photo.jpg --bio "Bio text..."
    python onboard_member.py "First Last" --website "https://example.com"
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

import openpyxl


def get_project_root() -> Path:
    return Path(__file__).parent.parent


def ensure_dependencies():
    try:
        import transformers
        import torch
    except ImportError:
        print("Installing required dependencies (transformers, torch, kernels)...")
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-q",
                "transformers",
                "torch",
                "kernels",
            ]
        )


def get_llm_pipeline():
    if not hasattr(get_llm_pipeline, "_pipeline"):
        ensure_dependencies()
        from transformers import pipeline

        print("Loading gpt-oss-20b model (this may take a moment on first run)...")
        get_llm_pipeline._pipeline = pipeline(
            "text-generation",
            model="openai/gpt-oss-20b",
            torch_dtype="auto",
            device_map="auto",
        )
    return get_llm_pipeline._pipeline


def generate_bio_with_llm(first_name: str, year: str) -> str:
    pipe = get_llm_pipeline()

    messages = [
        {
            "role": "user",
            "content": f'Write a single short sentence bio for a new undergraduate research assistant named {first_name} who joined a cognitive neuroscience memory research lab in {year}. Keep it generic and professional. Do not use pronouns. Maximum 20 words. Example: "Alex joined the lab in 2025 and is interested in how people learn and remember."',
        }
    ]

    result = pipe(messages, max_new_tokens=50)
    bio = result[0]["generated_text"][-1]["content"].strip()
    bio = bio.strip('"').strip()

    if not bio or len(bio) < 10:
        bio = f"{first_name} joined the lab in {year} and is interested in how people learn and remember."

    return bio


def edit_bio_with_llm(bio: str, first_name: str) -> str:
    pipe = get_llm_pipeline()

    messages = [
        {
            "role": "user",
            "content": f"""Edit this bio for a lab member named {first_name}. Follow these rules strictly:
1. Use only first name "{first_name}" (remove last name if present)
2. Fix any typos and grammar errors
3. Use Oxford commas
4. Keep to 3-4 sentences maximum
5. Remove any dangerous personal information (keep hometown/state/country if mentioned)
6. Remove any harmful content
7. Keep the tone professional and friendly

Original bio: "{bio}"

Return ONLY the edited bio, nothing else.""",
        }
    ]

    result = pipe(messages, max_new_tokens=200)
    edited = result[0]["generated_text"][-1]["content"].strip()
    edited = edited.strip('"').strip()

    if not edited or len(edited) < 10:
        return bio

    return edited


def parse_name(full_name: str) -> Tuple[str, str]:
    parts = full_name.strip().split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def find_photo(photo_hint: str, project_root: Path) -> Optional[Path]:
    search_dirs = [
        project_root,
        project_root / "images",
        project_root / "images" / "people",
        Path.home() / "Downloads",
        Path.home() / "Desktop",
    ]

    extensions = [".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"]

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for ext in extensions:
            candidate = search_dir / f"{photo_hint}{ext}"
            if candidate.exists():
                return candidate

    for ext in extensions:
        candidate = Path(f"{photo_hint}{ext}")
        if candidate.exists():
            return candidate

    return None


def process_photo(
    photo_path: Path, output_name: str, project_root: Path
) -> Optional[str]:
    output_dir = project_root / "images" / "people"
    output_file = output_dir / f"{output_name}.png"

    add_borders_script = project_root / "scripts" / "add_borders.py"

    print(f"  Processing photo with face detection...")
    result = subprocess.run(
        [
            sys.executable,
            str(add_borders_script),
            str(photo_path),
            str(output_dir),
            "--face",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"  Warning: Photo processing failed: {result.stderr}")
        return None

    processed_file = output_dir / f"{photo_path.stem}.png"
    if processed_file.exists() and processed_file != output_file:
        processed_file.rename(output_file)

    if output_file.exists():
        if photo_path != output_file and photo_path.suffix.lower() != ".png":
            try:
                photo_path.unlink()
                print(f"  Removed original photo: {photo_path}")
            except Exception as e:
                print(f"  Warning: Could not remove original photo: {e}")

        print(f"  Photo saved to: {output_file}")
        return f"{output_name}.png"

    return None


def member_exists_in_spreadsheet(
    xlsx_path: Path, name: str
) -> Tuple[bool, Optional[int]]:
    wb = openpyxl.load_workbook(xlsx_path)
    sheet = wb["members"]

    name_lower = name.lower()
    for row_idx, row in enumerate(
        sheet.iter_rows(min_row=2, values_only=True), start=2
    ):
        if row[1] and str(row[1]).lower() == name_lower:
            wb.close()
            return True, row_idx

    wb.close()
    return False, None


def add_to_spreadsheet(
    xlsx_path: Path, name: str, role: str, bio: str, image: str, website: str
) -> None:
    wb = openpyxl.load_workbook(xlsx_path)
    sheet = wb["members"]

    exists, row_idx = member_exists_in_spreadsheet(xlsx_path, name)
    wb.close()

    wb = openpyxl.load_workbook(xlsx_path)
    sheet = wb["members"]

    if exists:
        print(f"  Updating existing entry for {name} at row {row_idx}")
        if image:
            sheet.cell(row=row_idx, column=1, value=image)
        sheet.cell(row=row_idx, column=2, value=name)
        if website:
            sheet.cell(row=row_idx, column=3, value=website)
        sheet.cell(row=row_idx, column=4, value=role)
        if bio:
            sheet.cell(row=row_idx, column=5, value=bio)
    else:
        last_row = sheet.max_row
        while last_row > 1 and not any(
            sheet.cell(row=last_row, column=c).value for c in range(1, 7)
        ):
            last_row -= 1

        new_row = last_row + 1

        sheet.cell(row=new_row, column=1, value=image)
        sheet.cell(row=new_row, column=2, value=name)
        sheet.cell(row=new_row, column=3, value=website)
        sheet.cell(row=new_row, column=4, value=role)
        sheet.cell(row=new_row, column=5, value=bio)

        print(f"  Added new entry for {name} at row {new_row}")

    wb.save(xlsx_path)
    wb.close()


def member_exists_in_cv(cv_path: Path, name: str) -> bool:
    content = cv_path.read_text(encoding="utf-8")
    name_escaped = re.escape(name)
    pattern = r"\\item\s+" + name_escaped + r"\*?\s*\("
    return bool(re.search(pattern, content, re.IGNORECASE))


def add_to_cv(cv_path: Path, name: str, role: str, year: str) -> bool:
    content = cv_path.read_text(encoding="utf-8")

    if member_exists_in_cv(cv_path, name):
        print(f"  {name} already exists in CV, skipping")
        return True

    role_lower = role.lower()

    if "postdoc" in role_lower:
        section_pattern = (
            r"(\\textit\{Postdoctoral Advisees\}:\s*\n\\begin\{etaremune\})"
        )
        entry = f"\\item {name} ({year} -- )"
    elif "grad" in role_lower:
        section_pattern = r"(\\textit\{Graduate Advisees\}:\s*\n\\begin\{etaremune\})"
        entry = f"\\item {name} (Doctoral student; {year} -- )"
    else:
        section_pattern = r"(\\textit\{Undergraduate Advisees\}:\s*\n\\blfootnote\{[^}]*\}\s*\n\\begin\{multicols\}\{2\}\s*\n\\begin\{etaremune\})"
        entry = f"\\item {name} ({year} -- )"

    match = re.search(section_pattern, content)
    if not match:
        print(f"  Warning: Could not find section for {role} in CV")
        return False

    insert_pos = match.end()
    new_content = content[:insert_pos] + f"\n  {entry}" + content[insert_pos:]

    cv_path.write_text(new_content, encoding="utf-8")
    print(f"  Added {name} to CV under {role}")
    return True


def rebuild_pages(project_root: Path) -> None:
    scripts_dir = project_root / "scripts"

    print("\nRebuilding people.html...")
    result = subprocess.run(
        [sys.executable, "build_people.py"],
        cwd=scripts_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("  people.html rebuilt successfully")
    else:
        print(f"  Warning: build_people.py failed: {result.stderr}")

    print("\nRebuilding CV...")
    result = subprocess.run(
        [sys.executable, "build_cv.py"], cwd=scripts_dir, capture_output=True, text=True
    )
    if result.returncode == 0:
        print("  CV rebuilt successfully")
    else:
        print(f"  Note: CV rebuild requires LaTeX. Run manually if needed.")


def onboard_member(
    name: str,
    rank: str = "undergrad",
    photo: Optional[str] = None,
    bio: Optional[str] = None,
    website: Optional[str] = None,
    skip_rebuild: bool = False,
    skip_llm: bool = False,
) -> bool:
    project_root = get_project_root()
    xlsx_path = project_root / "data" / "people.xlsx"
    cv_path = project_root / "documents" / "JRM_CV.tex"

    first_name, last_name = parse_name(name)
    name_lower = name.lower()
    photo_base = (
        f"{first_name}_{last_name}".lower().replace(" ", "_")
        if last_name
        else first_name.lower()
    )
    current_year = str(datetime.now().year)

    print(f"\nOnboarding {name} as {rank}...")

    image_filename = None
    if photo is None:
        photo = photo_base

    photo_path = find_photo(photo, project_root)
    if photo_path:
        print(f"  Found photo: {photo_path}")
        image_filename = process_photo(photo_path, photo_base, project_root)
    else:
        existing_photo = project_root / "images" / "people" / f"{photo_base}.png"
        if existing_photo.exists():
            print(f"  Using existing photo: {existing_photo}")
            image_filename = f"{photo_base}.png"
        else:
            print(f"  No photo found for {photo}")

    if not skip_llm:
        if bio:
            print("  Editing bio with LLM...")
            bio = edit_bio_with_llm(bio, first_name)
            print(f"  Bio: {bio[:100]}...")
        else:
            print("  Generating bio with LLM...")
            bio = generate_bio_with_llm(first_name, current_year)
            print(f"  Bio: {bio}")
    elif not bio:
        bio = f"{first_name} joined the lab in {current_year} and is interested in how people learn and remember."

    print("\nUpdating spreadsheet...")
    add_to_spreadsheet(
        xlsx_path, name_lower, rank, bio, image_filename or "", website or ""
    )

    print("\nUpdating CV...")
    add_to_cv(cv_path, name, rank, current_year)

    if not skip_rebuild:
        rebuild_pages(project_root)

    print(f"\nSuccessfully onboarded {name}!")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Onboard new lab members.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python onboard_member.py "John Doe"
    python onboard_member.py "Jane Smith" --rank "grad student"
    python onboard_member.py "Bob Jones" --photo headshot --bio "Bob is interested in memory."
    python onboard_member.py "Alice Lee" --website "https://alice.com" --skip-llm
        """,
    )

    parser.add_argument("name", help='Full name of the new member (e.g., "First Last")')
    parser.add_argument(
        "--rank",
        "-r",
        default="undergrad",
        help="Role/rank (default: undergrad). Options: undergrad, grad student, postdoc",
    )
    parser.add_argument(
        "--photo",
        "-p",
        help="Photo filename without extension (default: first_last). Searches current dir, images/, Downloads/",
    )
    parser.add_argument(
        "--bio",
        "-b",
        help="Bio text (will be edited by LLM). If not provided, a generic bio is generated.",
    )
    parser.add_argument("--website", "-w", help="Personal website URL")
    parser.add_argument(
        "--skip-rebuild", action="store_true", help="Skip rebuilding HTML pages"
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM processing (use bio as-is or generate simple default)",
    )

    args = parser.parse_args()

    success = onboard_member(
        name=args.name,
        rank=args.rank,
        photo=args.photo,
        bio=args.bio,
        website=args.website,
        skip_rebuild=args.skip_rebuild,
        skip_llm=args.skip_llm,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
