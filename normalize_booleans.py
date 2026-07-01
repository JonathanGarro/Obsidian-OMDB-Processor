import os
import re
import csv
import shutil
import yaml
from pathlib import Path
from dotenv import load_dotenv

# load environment variables from .env file
load_dotenv()

# config
# MARKDOWN_DIRECTORY still points at the Film folder for the omdb scripts.
# this script needs Film and Television, so it steps up to the shared Culture parent.
CULTURE_ROOT = Path(os.getenv("MARKDOWN_DIRECTORY", "./markdown_files")).parent
SUBFOLDERS = ["Film", "Television"]
TARGET_FIELDS = ["rewatch"]
DRY_RUN = False
BACKUP_DIR = "backups"
AUDIT_CSV = os.path.join("outputs", "boolean_normalization_audit.csv")

YES_VALUES = {"yes", "y", "on"}
NO_VALUES = {"no", "n", "off"}


class StrictBoolLoader(yaml.SafeLoader):
    """yaml loader that only treats true/false as booleans, not yes/no/on/off.

    obsidian's yaml parser follows yaml 1.2 and leaves unquoted yes/no as text.
    pyyaml's default safe_load follows yaml 1.1 and silently converts yes/no/on/off
    to booleans, which corrupts frontmatter fields on any read-modify-write cycle.
    this loader matches obsidian's behavior so round-tripping is safe.
    """


StrictBoolLoader.add_implicit_resolver(
    'tag:yaml.org,2002:bool',
    re.compile(r'^(?:true|True|TRUE|false|False|FALSE)$'),
    list('tTfF')
)
StrictBoolLoader.yaml_implicit_resolvers = {
    key: [
        (tag, regexp) for tag, regexp in resolvers
        if tag != 'tag:yaml.org,2002:bool' or key in 'tTfF'
    ]
    for key, resolvers in StrictBoolLoader.yaml_implicit_resolvers.items()
}


def extract_frontmatter_and_content(file_content):
    """extract yaml frontmatter and remaining content from markdown file"""
    pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
    match = re.match(pattern, file_content, re.DOTALL)

    if match:
        frontmatter = yaml.load(match.group(1), Loader=StrictBoolLoader) or {}
        content = match.group(2)
        return frontmatter, content
    return {}, file_content


def normalize_value(value):
    """convert a yes/no/on/off style string to a real boolean, else return unchanged"""
    if isinstance(value, bool):
        return value, False

    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in YES_VALUES:
            return True, True
        if lowered in NO_VALUES:
            return False, True

    return value, False


def normalize_file(file_path):
    """check a file for target fields needing normalization, optionally write changes"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    frontmatter, body = extract_frontmatter_and_content(content)

    changes = []
    for field in TARGET_FIELDS:
        if field not in frontmatter:
            continue

        old_value = frontmatter[field]
        new_value, changed = normalize_value(old_value)

        if changed:
            changes.append((field, old_value, new_value))
            frontmatter[field] = new_value

    if not changes:
        return changes

    if not DRY_RUN:
        relative_path = file_path.relative_to(CULTURE_ROOT)
        backup_path = os.path.join(BACKUP_DIR, relative_path)
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        shutil.copy2(file_path, backup_path)

        new_content = f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---\n{body}"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

    return changes


def process_markdown_files(root, subfolders):
    """process markdown files in each configured subfolder, auditing and optionally fixing target fields"""
    markdown_files = []
    for subfolder in subfolders:
        markdown_files.extend(Path(root, subfolder).rglob('*.md'))

    audit_rows = []
    changed_count = 0
    unchanged_count = 0

    for file_path in markdown_files:
        changes = normalize_file(file_path)

        if changes:
            changed_count += 1
            for field, old_value, new_value in changes:
                audit_rows.append([file_path.relative_to(root), field, old_value, new_value])
        else:
            unchanged_count += 1

    os.makedirs("outputs", exist_ok=True)
    with open(AUDIT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['filename', 'field', 'old_value', 'new_value'])
        writer.writerows(audit_rows)

    mode = "dry run - no files written" if DRY_RUN else "live run - files updated"
    print(f"mode: {mode}")
    print(f"scanned: {len(markdown_files)} files across {subfolders}")
    print(f"files needing changes: {changed_count}")
    print(f"files unchanged: {unchanged_count}")
    print(f"audit written to: {AUDIT_CSV}")

    if DRY_RUN and changed_count > 0:
        print("\nreview the audit csv, then set DRY_RUN = False to apply changes")

    if not DRY_RUN and changed_count > 0:
        print(f"originals backed up to: {BACKUP_DIR}/")


# usage
if __name__ == "__main__":
    print(f"normalizing boolean fields {TARGET_FIELDS} in {SUBFOLDERS} under {CULTURE_ROOT}\n")
    process_markdown_files(CULTURE_ROOT, SUBFOLDERS)
    print("\ndone - remember to reload obsidian to see changes")