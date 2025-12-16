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


def extract_url_from_markdown_link(link_value):
    """extract url from markdown link format [text](url)"""
    if not link_value:
        return link_value

    # check if it's a markdown link format
    pattern = r'\[.*?\]\((https://www\.imdb\.com/title/[^\)]+)\)'
    match = re.match(pattern, link_value)

    if match:
        # return just the url
        return match.group(1)

    # if it's already just a url, return as-is
    return link_value


def fix_imdb_link(file_path):
    """fix imdb_link in markdown file frontmatter"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    frontmatter, body = extract_frontmatter_and_content(content)

    # check if imdb_link exists and needs fixing
    if 'imdb_link' in frontmatter:
        original_link = frontmatter['imdb_link']
        fixed_link = extract_url_from_markdown_link(original_link)

        if original_link != fixed_link:
            frontmatter['imdb_link'] = fixed_link

            # write updated content back to file
            new_content = f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---\n{body}"

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            return True

    return False


def process_markdown_files(directory):
    """process all markdown files in directory"""
    markdown_files = Path(directory).glob('*.md')

    fixed_count = 0
    skipped_count = 0

    for file_path in markdown_files:
        print(f"checking: {file_path.name}")

        was_fixed = fix_imdb_link(file_path)

        if was_fixed:
            print(f"  fixed imdb_link in {file_path.name}")
            fixed_count += 1
        else:
            skipped_count += 1

    print(f"\nsummary: {fixed_count} files fixed, {skipped_count} files unchanged")


# usage
if __name__ == "__main__":
    DIRECTORY = os.getenv("MARKDOWN_DIRECTORY", "./markdown_files")

    print(f"processing markdown files in: {DIRECTORY}\n")
    process_markdown_files(DIRECTORY)