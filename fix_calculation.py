import os
import re
import yaml
from pathlib import Path
from dotenv import load_dotenv

# load environment variables from .env file
load_dotenv()


def extract_frontmatter_and_content(file_content):
    """extract yaml frontmatter and remaining content from markdown file"""
    pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
    match = re.match(pattern, file_content, re.DOTALL)

    if match:
        frontmatter = yaml.safe_load(match.group(1)) or {}
        content = match.group(2)
        return frontmatter, content
    return {}, file_content


def calculate_rating_delta_correct(rating, rotten_tomatoes):
    """calculate delta between user rating and rotten tomatoes score (corrected)"""
    if rating is None or rotten_tomatoes is None:
        return None

    try:
        # convert rating to percentage (out of 100) - rating is 0-5 scale
        my_rating_percent = float(rating) * 20

        # parse rotten tomatoes score (remove % and convert to int)
        rt_score = int(rotten_tomatoes.rstrip('%'))

        # calculate delta
        delta = int(my_rating_percent - rt_score)
        return delta
    except (ValueError, AttributeError):
        return None


def fix_rating_delta(file_path):
    """fix the my_rating_delta calculation in a markdown file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    frontmatter, body = extract_frontmatter_and_content(content)

    # check if file has the necessary fields
    if 'rating' not in frontmatter or 'rotten_tomatoes' not in frontmatter:
        return False

    # recalculate the delta
    old_delta = frontmatter.get('my_rating_delta')
    new_delta = calculate_rating_delta_correct(frontmatter['rating'], frontmatter['rotten_tomatoes'])

    if new_delta is not None:
        frontmatter['my_rating_delta'] = new_delta

        # write updated content back to file
        new_content = f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---\n{body}"

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print(f"fixed {file_path.name}: {old_delta} -> {new_delta}")
        return True

    return False


def process_markdown_files(directory):
    """process all markdown files in directory to fix rating delta"""
    markdown_files = Path(directory).glob('*.md')

    fixed_count = 0
    skipped_count = 0

    for file_path in markdown_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        frontmatter, _ = extract_frontmatter_and_content(content)

        # only process files that have my_rating_delta
        if 'my_rating_delta' in frontmatter:
            if fix_rating_delta(file_path):
                fixed_count += 1
        else:
            skipped_count += 1

    print(f"\nsummary: {fixed_count} files fixed, {skipped_count} files skipped")


# usage
if __name__ == "__main__":
    DIRECTORY = os.getenv("MARKDOWN_DIRECTORY", "./markdown_files")

    print(f"fixing rating delta calculations in {DIRECTORY}")
    process_markdown_files(DIRECTORY)
    print("\ndone - remember to reload obsidian to see changes")