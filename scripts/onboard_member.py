#!/usr/bin/env python3
"""Onboard new lab members.

This script:
1. Checks if member is an alumni (and reactivates them if so)
2. Processes photo with hand-drawn border (if provided)
3. Generates or edits bio using local LLM (gpt-oss-20b)
4. Adds member to people.xlsx
5. Adds member to JRM_CV.tex
6. Invites to GitHub organization (if --github provided)
7. Shares Google Calendars (if --gmail provided)
8. Rebuilds people.html

Idempotent: Running twice with same name will update existing entry.
Reactivation: Running on an alumni will move them back to active status.

Usage:
    python onboard_member.py "First Last"
    python onboard_member.py "First Last" --rank "grad student"
    python onboard_member.py "First Last" --photo photo.jpg --bio "Bio text..."
    python onboard_member.py "First Last" --website "https://example.com"
    python onboard_member.py "First Last" --github username --teams "supereeg,hypertools"
    python onboard_member.py "First Last" --gmail user@gmail.com
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

import openpyxl

# =============================================================================
# Constants
# =============================================================================

GITHUB_ORG = "ContextLab"
CREDENTIALS_DIR = Path.home() / ".config" / "cdl"
GOOGLE_CREDENTIALS_FILE = CREDENTIALS_DIR / "google-credentials.json"

# Google Calendar IDs (from lab manual)
CALENDARS = {
    "contextual dynamics lab": {
        "id": "5ta50cfv4uih0a0k8m2di9dhjo@group.calendar.google.com",
        "undergrad_role": "reader",  # read-only for undergrads
        "default_role": "writer",  # write for grads/postdocs
    },
    "cdl resources": {
        "id": "dgcv8l8a8s10hfg2s5h0qec0q0@group.calendar.google.com",
        "undergrad_role": "writer",
        "default_role": "writer",
    },
    "out of lab": {
        "id": "h1j06dohcg7v1g2o5tkb7ijhvs@group.calendar.google.com",
        "undergrad_role": "writer",
        "default_role": "writer",
    },
}


def get_project_root() -> Path:
    return Path(__file__).parent.parent


def fuzzy_match_team(query: str, team_names: List[str]) -> Optional[str]:
    """Match team name using fuzzy matching (case-insensitive, space-insensitive)."""
    query_normalized = query.lower().replace(" ", "").replace("-", "").replace("_", "")

    for team in team_names:
        team_normalized = (
            team.lower().replace(" ", "").replace("-", "").replace("_", "")
        )
        if query_normalized == team_normalized:
            return team

    best_match = None
    best_ratio = 0.6
    for team in team_names:
        team_normalized = (
            team.lower().replace(" ", "").replace("-", "").replace("_", "")
        )
        ratio = SequenceMatcher(None, query_normalized, team_normalized).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = team

    return best_match


def get_github_teams() -> Dict[str, int]:
    """Get all teams in the ContextLab organization with their IDs."""
    result = subprocess.run(
        ["gh", "api", f"/orgs/{GITHUB_ORG}/teams", "--paginate"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  Warning: Could not fetch GitHub teams: {result.stderr}")
        return {}

    teams = json.loads(result.stdout)
    return {team["name"]: team["id"] for team in teams}


def is_github_org_member(username: str) -> bool:
    """Check if user is already a member of the organization."""
    result = subprocess.run(
        ["gh", "api", f"/orgs/{GITHUB_ORG}/members/{username}"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def get_pending_invitations() -> List[str]:
    """Get list of usernames with pending org invitations."""
    result = subprocess.run(
        ["gh", "api", f"/orgs/{GITHUB_ORG}/invitations", "--paginate"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []

    invitations = json.loads(result.stdout)
    return [inv.get("login", "") for inv in invitations if inv.get("login")]


def invite_to_github_org(username: str, team_names: Optional[List[str]] = None) -> bool:
    """Invite user to GitHub org and add to specified teams."""
    print(f"\n  GitHub: Processing {username}...")

    if is_github_org_member(username):
        print(f"    {username} is already an org member")
        if team_names:
            return add_to_github_teams(username, team_names)
        return True

    pending = get_pending_invitations()
    if username.lower() in [p.lower() for p in pending]:
        print(f"    {username} already has a pending invitation")
        return True

    all_teams = get_github_teams()
    if not all_teams:
        print("    Warning: Could not fetch teams, inviting without team assignment")

    teams_to_add = ["Lab default"]
    if team_names:
        for requested_team in team_names:
            matched = fuzzy_match_team(requested_team, list(all_teams.keys()))
            if matched and matched not in teams_to_add:
                teams_to_add.append(matched)
                if matched != requested_team:
                    print(f"    Matched '{requested_team}' -> '{matched}'")
            elif not matched:
                print(f"    Warning: No match found for team '{requested_team}'")

    team_ids = [all_teams[t] for t in teams_to_add if t in all_teams]

    cmd = [
        "gh",
        "api",
        "-X",
        "POST",
        f"/orgs/{GITHUB_ORG}/invitations",
        "-f",
        f"invitee_id={get_github_user_id(username)}",
        "-f",
        "role=direct_member",
    ]
    for tid in team_ids:
        cmd.extend(["-F", f"team_ids[]={tid}"])

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        if "invitee_id" in result.stderr or "user_id" in result.stderr:
            cmd_email = [
                "gh",
                "api",
                "-X",
                "POST",
                f"/orgs/{GITHUB_ORG}/invitations",
                "-f",
                f"email={username}@users.noreply.github.com",
                "-f",
                "role=direct_member",
            ]
            for tid in team_ids:
                cmd_email.extend(["-F", f"team_ids[]={tid}"])
            result = subprocess.run(cmd_email, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"    Error inviting to org: {result.stderr}")
            return False

    print(f"    Invited {username} to {GITHUB_ORG}")
    print(f"    Teams: {', '.join(teams_to_add)}")
    return True


def get_github_user_id(username: str) -> Optional[int]:
    """Get GitHub user ID from username."""
    result = subprocess.run(
        ["gh", "api", f"/users/{username}", "--jq", ".id"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        try:
            return int(result.stdout.strip())
        except ValueError:
            pass
    return None


def add_to_github_teams(username: str, team_names: List[str]) -> bool:
    """Add existing org member to additional teams."""
    all_teams = get_github_teams()
    success = True

    for requested_team in team_names:
        matched = fuzzy_match_team(requested_team, list(all_teams.keys()))
        if not matched:
            print(f"    Warning: No match found for team '{requested_team}'")
            continue

        team_slug = matched.lower().replace(" ", "-")
        result = subprocess.run(
            [
                "gh",
                "api",
                "-X",
                "PUT",
                f"/orgs/{GITHUB_ORG}/teams/{team_slug}/memberships/{username}",
                "-f",
                "role=member",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print(f"    Added to team: {matched}")
        else:
            print(f"    Warning: Could not add to {matched}: {result.stderr}")
            success = False

    return success


def setup_google_credentials() -> bool:
    """Check for Google credentials and provide setup instructions if missing."""
    if GOOGLE_CREDENTIALS_FILE.exists():
        return True

    print("\n" + "=" * 60)
    print("GOOGLE CALENDAR SETUP REQUIRED")
    print("=" * 60)
    print(f"""
To share Google Calendars, you need a service account:

1. Go to https://console.cloud.google.com/
2. Create a project (or use existing CDL project)
3. Enable the Google Calendar API
4. Create a Service Account:
   - Go to IAM & Admin > Service Accounts
   - Create service account named 'cdl-onboarding-bot'
   - Create a JSON key and download it
5. Share each calendar with the service account email:
   - Open Google Calendar settings for each calendar
   - Add the service account email with 'Make changes to events'

6. Save the JSON key file to:
   {GOOGLE_CREDENTIALS_FILE}

Create the directory if needed:
   mkdir -p {CREDENTIALS_DIR}
   mv ~/Downloads/your-key-file.json {GOOGLE_CREDENTIALS_FILE}
   chmod 600 {GOOGLE_CREDENTIALS_FILE}
""")
    print("=" * 60)
    return False


def get_calendar_service():
    """Get authenticated Google Calendar service."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        print("  Installing Google API dependencies...")
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-q",
                "google-api-python-client",
                "google-auth",
            ]
        )
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        str(GOOGLE_CREDENTIALS_FILE),
        scopes=["https://www.googleapis.com/auth/calendar"],
    )
    return build("calendar", "v3", credentials=creds)


def get_calendar_acl(service, calendar_id: str, email: str) -> Optional[str]:
    """Check if user already has access to calendar. Returns role or None."""
    try:
        acl_list = service.acl().list(calendarId=calendar_id).execute()
        for rule in acl_list.get("items", []):
            if rule.get("scope", {}).get("value", "").lower() == email.lower():
                return rule.get("role")
    except Exception:
        pass
    return None


def share_calendar(
    service, calendar_id: str, email: str, role: str, calendar_name: str
) -> bool:
    """Share a calendar with a user."""
    existing_role = get_calendar_acl(service, calendar_id, email)

    if existing_role:
        if existing_role == role:
            print(f"    {calendar_name}: already has {role} access")
            return True
        else:
            print(f"    {calendar_name}: has {existing_role}, updating to {role}")

    acl_rule = {
        "scope": {"type": "user", "value": email},
        "role": role,
    }

    try:
        if existing_role:
            rule_id = f"user:{email}"
            service.acl().update(
                calendarId=calendar_id, ruleId=rule_id, body=acl_rule
            ).execute()
        else:
            service.acl().insert(
                calendarId=calendar_id, body=acl_rule, sendNotifications=True
            ).execute()

        role_desc = "read" if role == "reader" else "write"
        print(f"    {calendar_name}: granted {role_desc} access")
        return True

    except Exception as e:
        print(f"    {calendar_name}: Error - {e}")
        return False


def share_google_calendars(email: str, rank: str) -> bool:
    """Share all lab calendars with appropriate permissions based on rank."""
    if not setup_google_credentials():
        return False

    print(f"\n  Google Calendar: Sharing with {email}...")

    try:
        service = get_calendar_service()
    except Exception as e:
        print(f"    Error connecting to Google Calendar API: {e}")
        return False

    is_undergrad = "undergrad" in rank.lower()
    success = True

    for cal_name, cal_info in CALENDARS.items():
        role = cal_info["undergrad_role"] if is_undergrad else cal_info["default_role"]
        if not share_calendar(service, cal_info["id"], email, role, cal_name):
            success = False

    return success


LLM_VENV_DIR = Path.home() / ".cache" / "cdl" / "llm-venv"


def get_llm_venv_python() -> Optional[Path]:
    """Get the Python executable from the LLM virtual environment."""
    if sys.platform == "win32":
        python_path = LLM_VENV_DIR / "Scripts" / "python.exe"
    else:
        python_path = LLM_VENV_DIR / "bin" / "python"
    return python_path if python_path.exists() else None


def setup_llm_venv() -> Optional[Path]:
    """Create isolated venv for LLM to avoid dependency conflicts."""
    if get_llm_venv_python():
        return get_llm_venv_python()

    print("  Creating isolated LLM environment (one-time setup)...")
    LLM_VENV_DIR.parent.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.check_call(
            [sys.executable, "-m", "venv", str(LLM_VENV_DIR)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as e:
        print(f"  Warning: Could not create venv: {e}")
        return None

    venv_python = get_llm_venv_python()
    if not venv_python:
        print("  Warning: venv created but Python not found")
        return None

    print("  Installing LLM dependencies (this may take a few minutes)...")
    try:
        subprocess.check_call(
            [str(venv_python), "-m", "pip", "install", "-q", "--upgrade", "pip"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.check_call(
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "-q",
                "mlx-lm",
            ],
            stdout=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as e:
        print(f"  Warning: Could not install LLM dependencies: {e}")
        return None

    print("  LLM environment ready")
    return venv_python


def run_llm_in_venv(script: str, timeout: int = 600) -> Optional[str]:
    """Run LLM script in isolated venv and return output."""
    venv_python = setup_llm_venv()
    if not venv_python:
        return None

    try:
        result = subprocess.run(
            [str(venv_python), "-c", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            print(f"  LLM error: {result.stderr[:200]}")
            return None
    except subprocess.TimeoutExpired:
        print("  Warning: LLM operation timed out")
        return None
    except Exception as e:
        print(f"  Warning: LLM operation failed: {e}")
        return None

    if not ensure_llm_dependencies():
        return None

    from transformers import pipeline

    print("  Loading gpt-oss-20b model (this may take a moment on first run)...")
    try:
        _llm_pipeline_cache = pipeline(
            "text-generation",
            model="openai/gpt-oss-20b",
            torch_dtype="auto",
            device_map="auto",
        )
    except Exception as e:
        print(f"  Warning: Could not load LLM model: {e}")
        print("  Using fallback bio generation.")
        return None

    return _llm_pipeline_cache


LLM_MODEL = "mlx-community/Qwen2.5-32B-Instruct-4bit"


def generate_bio_with_llm(first_name: str, year: str) -> str:
    fallback = f"{first_name} joined the lab in {year} and is interested in how people learn and remember."

    script = f'''
import warnings
warnings.filterwarnings("ignore")
from mlx_lm import load, generate

model, tokenizer = load("{LLM_MODEL}")

prompt = tokenizer.apply_chat_template(
    [{{"role": "user", "content": "Write a single sentence professional bio for {first_name}, an undergraduate who joined a cognitive neuroscience memory research lab in {year}. Keep it generic. Do not use pronouns. Maximum 25 words. Output ONLY the bio sentence, nothing else."}}],
    tokenize=False,
    add_generation_prompt=True
)

bio = generate(model, tokenizer, prompt=prompt, max_tokens=60)
bio = bio.strip('"').strip()
if bio and len(bio) > 15 and not bio.lower().startswith("here") and not bio.lower().startswith("sure"):
    print(bio)
else:
    print("")
'''

    print("  Generating bio with LLM...")
    result = run_llm_in_venv(script)
    if result and len(result) > 15:
        return result
    return fallback


def edit_bio_with_llm(bio: str, first_name: str) -> str:
    bio_escaped = (
        bio.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace('"', '\\"')
        .replace("\n", " ")
    )

    script = f'''
import warnings
warnings.filterwarnings("ignore")
from mlx_lm import load, generate

model, tokenizer = load("{LLM_MODEL}")

prompt = tokenizer.apply_chat_template(
    [{{"role": "user", "content": """Edit this bio. Rules:
1. Use only first name "{first_name}" (remove last name)
2. Fix typos and grammar  
3. Keep 1-3 sentences max
4. Remove dangerous personal info (SSN, addresses, phone numbers)
5. Keep professional and friendly tone

Original: "{bio_escaped}"

Output ONLY the edited bio, nothing else:"""}}],
    tokenize=False,
    add_generation_prompt=True
)

edited = generate(model, tokenizer, prompt=prompt, max_tokens=150)
edited = edited.strip('"').strip()
if edited and len(edited) > 15 and not edited.lower().startswith("here") and not edited.lower().startswith("edited"):
    print(edited)
else:
    print("")
'''

    print("  Editing bio with LLM...")
    result = run_llm_in_venv(script)
    if result and len(result) > 15:
        return result
    return bio


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


def photo_already_processed(photo_base: str, project_root: Path) -> bool:
    processed_photo = project_root / "images" / "people" / f"{photo_base}.png"
    return processed_photo.exists()


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


def get_existing_bio(xlsx_path: Path, name: str) -> Optional[str]:
    wb = openpyxl.load_workbook(xlsx_path)
    sheet = wb["members"]

    name_lower = name.lower()
    for row in sheet.iter_rows(min_row=2, values_only=True):
        if row[1] and str(row[1]).lower() == name_lower:
            bio = row[4] if len(row) > 4 else None
            wb.close()
            if bio and len(str(bio)) > 10:
                return str(bio)
            return None

    wb.close()
    return None


def find_alumni_entry(xlsx_path: Path, name: str) -> Optional[Dict[str, Any]]:
    """Find alumni entry across all alumni sheets. Returns dict with sheet name, row, and data."""
    wb = openpyxl.load_workbook(xlsx_path)
    name_lower = name.lower()
    name_title = name.title().lower()

    alumni_sheets = [
        "alumni_postdocs",
        "alumni_grads",
        "alumni_managers",
        "alumni_undergrads",
    ]

    for sheet_name in alumni_sheets:
        if sheet_name not in wb.sheetnames:
            continue
        sheet = wb[sheet_name]
        headers = [cell.value for cell in sheet[1]]

        for row_idx, row in enumerate(
            sheet.iter_rows(min_row=2, values_only=True), start=2
        ):
            if not row[0]:
                continue
            row_name = str(row[0]).lower()
            if row_name == name_lower or row_name == name_title:
                entry: Dict[str, Any] = {
                    "sheet": sheet_name,
                    "row_idx": row_idx,
                    "name": row[0],
                }
                for i, header in enumerate(headers):
                    if header and i < len(row):
                        entry[str(header)] = row[i]
                wb.close()
                return entry

    wb.close()
    return None


def remove_from_alumni(xlsx_path: Path, alumni_entry: Dict[str, Any]) -> None:
    """Remove an entry from the alumni sheet."""
    wb = openpyxl.load_workbook(xlsx_path)
    sheet = wb[alumni_entry["sheet"]]
    sheet.delete_rows(alumni_entry["row_idx"])
    wb.save(xlsx_path)
    wb.close()
    print(f"  Removed {alumni_entry['name']} from {alumni_entry['sheet']}")


def get_bio_from_git_history(
    xlsx_path: Path, name: str, project_root: Path
) -> Optional[str]:
    """Search git history for old bio in people.xlsx."""
    name_lower = name.lower()
    name_title = name.title().lower()

    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--oneline",
                "--follow",
                "--",
                str(xlsx_path.relative_to(project_root)),
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None

        commits = [
            line.split()[0] for line in result.stdout.strip().split("\n") if line
        ]

        for commit in commits[:20]:  # Limit to last 20 commits
            try:
                with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                    tmp_path = tmp.name

                extract_result = subprocess.run(
                    ["git", "show", f"{commit}:{xlsx_path.relative_to(project_root)}"],
                    cwd=project_root,
                    capture_output=True,
                )
                if extract_result.returncode != 0:
                    continue

                with open(tmp_path, "wb") as f:
                    f.write(extract_result.stdout)

                wb = openpyxl.load_workbook(tmp_path)
                if "members" in wb.sheetnames:
                    sheet = wb["members"]
                    for row in sheet.iter_rows(min_row=2, values_only=True):
                        if row[1] and str(row[1]).lower() in [name_lower, name_title]:
                            bio = row[4] if len(row) > 4 else None
                            if bio and len(str(bio)) > 10:
                                wb.close()
                                Path(tmp_path).unlink(missing_ok=True)
                                print(
                                    f"  Found old bio in git history (commit {commit})"
                                )
                                return str(bio)
                wb.close()
                Path(tmp_path).unlink(missing_ok=True)

            except Exception:
                continue

    except Exception as e:
        print(f"  Note: Could not search git history: {e}")

    return None


def add_to_spreadsheet(
    xlsx_path: Path, name: str, role: str, bio: str, image: str, website: str
) -> None:
    wb = openpyxl.load_workbook(xlsx_path)
    sheet = wb["members"]

    exists, row_idx = member_exists_in_spreadsheet(xlsx_path, name)
    wb.close()

    wb = openpyxl.load_workbook(xlsx_path)
    sheet = wb["members"]

    if exists and row_idx is not None:
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


def cv_entry_has_end_date(cv_path: Path, name: str) -> bool:
    """Check if CV entry has an end date (closed range)."""
    content = cv_path.read_text(encoding="utf-8")
    name_escaped = re.escape(name)
    # Match: \item Name (YYYY -- YYYY) or \item Name (YYYY) but NOT \item Name (YYYY -- )
    pattern_closed = r"\\item\s+" + name_escaped + r"\*?\s*\(\d{4}\s*--\s*\d{4}\)"
    pattern_single = r"\\item\s+" + name_escaped + r"\*?\s*\(\d{4}\)"
    pattern_open = r"\\item\s+" + name_escaped + r"\*?\s*\(\d{4}\s*--\s*\)"

    has_open = bool(re.search(pattern_open, content, re.IGNORECASE))
    has_closed = bool(re.search(pattern_closed, content, re.IGNORECASE))
    has_single = (
        bool(re.search(pattern_single, content, re.IGNORECASE))
        and not has_open
        and not has_closed
    )

    return has_closed or has_single


def reopen_cv_entry(cv_path: Path, name: str) -> bool:
    """Remove end date from CV entry: (YYYY -- YYYY) -> (YYYY -- ) or (YYYY) -> (YYYY -- )."""
    content = cv_path.read_text(encoding="utf-8")
    name_escaped = re.escape(name)

    # Pattern for closed range: (YYYY -- YYYY)
    pattern_closed = (
        r"(\\item\s+" + name_escaped + r"\*?\s*\()(\d{4})(\s*--\s*)(\d{4})(\))"
    )
    # Pattern for single year: (YYYY) - but not (YYYY -- )
    pattern_single = r"(\\item\s+" + name_escaped + r"\*?\s*\()(\d{4})(\))(?!\s*--)"

    def reopen_closed(match):
        prefix = match.group(1)
        start_year = match.group(2)
        suffix = match.group(5)
        return f"{prefix}{start_year} -- {suffix}"

    def reopen_single(match):
        prefix = match.group(1)
        year = match.group(2)
        suffix = match.group(3)
        return f"{prefix}{year} -- {suffix}"

    new_content, count = re.subn(
        pattern_closed, reopen_closed, content, flags=re.IGNORECASE
    )
    if count == 0:
        new_content, count = re.subn(
            pattern_single, reopen_single, content, flags=re.IGNORECASE
        )

    if count > 0:
        cv_path.write_text(new_content, encoding="utf-8")
        print(f"  Reopened CV entry for {name}")
        return True

    return False


def add_to_cv(cv_path: Path, name: str, role: str, year: str) -> bool:
    content = cv_path.read_text(encoding="utf-8")

    if member_exists_in_cv(cv_path, name):
        if cv_entry_has_end_date(cv_path, name):
            print(f"  {name} exists in CV with end date, reopening...")
            return reopen_cv_entry(cv_path, name)
        print(f"  {name} already exists in CV with open date, skipping")
        return True

    role_lower = role.lower()

    if "postdoc" in role_lower:
        section_pattern = (
            r"(\\textit\{Postdoctoral Advisees\}:\s*\n\\begin\{etaremune\})"
        )
        entry = f"\\item {name} ({year} -- )"
    elif "grad" in role_lower and "undergrad" not in role_lower:
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
    github_username: Optional[str] = None,
    github_teams: Optional[List[str]] = None,
    gmail: Optional[str] = None,
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

    alumni_entry = find_alumni_entry(xlsx_path, name)
    is_reactivation = alumni_entry is not None

    if is_reactivation:
        print(f"  Found {name} in {alumni_entry['sheet']} - reactivating...")
        remove_from_alumni(xlsx_path, alumni_entry)

    image_filename = None

    if photo_already_processed(photo_base, project_root):
        print(f"  Using existing processed photo: {photo_base}.png")
        image_filename = f"{photo_base}.png"
    else:
        if photo is None:
            photo = photo_base

        photo_path = find_photo(photo, project_root)
        if photo_path:
            print(f"  Found photo: {photo_path}")
            image_filename = process_photo(photo_path, photo_base, project_root)
        else:
            print(f"  No photo found for {photo}")

    if bio is None and is_reactivation:
        print("  Searching git history for old bio...")
        bio = get_bio_from_git_history(xlsx_path, name, project_root)

    if bio is None:
        existing_bio = get_existing_bio(xlsx_path, name)
        if existing_bio:
            print(f"  Using existing bio from spreadsheet")
            bio = existing_bio

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

    # Update lab-manual (best-effort; failure doesn't block onboarding)
    try:
        from parse_lab_manual import add_member_to_lab_manual, commit_and_push_lab_manual
        lab_manual_tex = project_root / 'lab-manual' / 'lab_manual.tex'
        if lab_manual_tex.exists():
            print("\nUpdating lab-manual...")
            add_member_to_lab_manual(lab_manual_tex, name, rank, current_year)
            try:
                commit_and_push_lab_manual(
                    project_root / 'lab-manual',
                    f"Onboard {name}"
                )
                print(f"  Updated lab-manual and pushed to remote")
            except RuntimeError as e:
                print(f"  WARNING: Lab-manual updated locally but push failed: {e}")
        else:
            print("  NOTE: Lab-manual submodule not found, skipping lab-manual update")
    except Exception as e:
        print(f"  WARNING: Could not update lab-manual: {e}")

    if github_username:
        invite_to_github_org(github_username, github_teams)

    if gmail:
        share_google_calendars(gmail, rank)

    if not skip_rebuild:
        rebuild_pages(project_root)

    action = "reactivated" if is_reactivation else "onboarded"
    print(f"\nSuccessfully {action} {name}!")
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

    # GitHub integration (invite to org and teams)
    python onboard_member.py "John Doe" --github johndoe
    python onboard_member.py "John Doe" --github johndoe --teams "supereeg,hypertools"

    # Google Calendar integration (share lab calendars)
    python onboard_member.py "John Doe" --gmail john.doe@gmail.com

    # Full onboarding with all integrations
    python onboard_member.py "John Doe" --rank "grad student" --github johndoe --gmail john@gmail.com
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
        "--github",
        "-g",
        help="GitHub username. If provided, invites to ContextLab org (adds to 'Lab default' team).",
    )
    parser.add_argument(
        "--teams",
        "-t",
        help="Comma-separated list of additional GitHub teams (uses fuzzy matching). E.g., 'supereeg,hypertools'",
    )
    parser.add_argument(
        "--gmail",
        help="Gmail address. If provided, shares lab calendars (undergrads get read access to main calendar, others get write).",
    )
    parser.add_argument(
        "--skip-rebuild", action="store_true", help="Skip rebuilding HTML pages"
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM processing (use bio as-is or generate simple default)",
    )

    args = parser.parse_args()

    github_teams = None
    if args.teams:
        github_teams = [t.strip() for t in args.teams.split(",") if t.strip()]

    success = onboard_member(
        name=args.name,
        rank=args.rank,
        photo=args.photo,
        bio=args.bio,
        website=args.website,
        github_username=args.github,
        github_teams=github_teams,
        gmail=args.gmail,
        skip_rebuild=args.skip_rebuild,
        skip_llm=args.skip_llm,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
