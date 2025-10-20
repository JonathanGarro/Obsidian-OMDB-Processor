import os
import re
import requests
import yaml
import csv
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


def extract_first_h1(content):
    """find the first h1 heading in markdown content"""
    match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
    return match.group(1).strip() if match else None


def has_movie_data(frontmatter):
    """check if frontmatter already contains movie data"""
    movie_keys = ['imdb_rating', 'imdb_votes', 'metascore', 'rotten_tomatoes', 'imdb_id', 'imdb_link']
    return any(key in frontmatter for key in movie_keys)


def search_omdb(title, api_key):
    """search omdb api for movie data"""
    url = f"http://www.omdbapi.com/?t={title}&apikey={api_key}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        if data.get('Response') == 'True':
            return data
    return None


def calculate_rating_delta(rating, rotten_tomatoes):
    """calculate delta between user rating and rotten tomatoes score"""
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


def update_markdown_file(file_path, movie_data):
    """update markdown file with movie data in frontmatter"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    frontmatter, body = extract_frontmatter_and_content(content)

    # add movie data to frontmatter
    if movie_data:
        imdb_id = movie_data.get('imdbID')

        frontmatter['imdb_id'] = imdb_id
        frontmatter[
            'imdb_link'] = f"[{movie_data.get('Title')} on IMDB](https://www.imdb.com/title/{imdb_id}/)" if imdb_id else None
        frontmatter['imdb_rating'] = movie_data.get('imdbRating')
        frontmatter['imdb_votes'] = movie_data.get('imdbVotes')
        frontmatter['metascore'] = movie_data.get('Metascore')
        frontmatter['rotten_tomatoes'] = None

        # extract rotten tomatoes score if available
        ratings = movie_data.get('Ratings', [])
        for rating in ratings:
            if rating['Source'] == 'Rotten Tomatoes':
                frontmatter['rotten_tomatoes'] = rating['Value']

        # calculate rating delta if user rating exists
        if 'rating' in frontmatter:
            delta = calculate_rating_delta(frontmatter['rating'], frontmatter['rotten_tomatoes'])
            if delta is not None:
                frontmatter['my_rating_delta'] = delta

    # write updated content back to file
    new_content = f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---\n{body}"

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)


def add_to_missing_csv(filename, title, csv_path):
    """add missing movie to csv file"""
    file_exists = os.path.isfile(csv_path)

    with open(csv_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['filename', 'movie_title', 'imdb_id'])
        writer.writerow([filename, title, ''])


def process_markdown_files(directory, api_key):
    """process all markdown files in directory"""
    markdown_files = Path(directory).glob('*.md')

    processed_count = 0
    skipped_count = 0
    missing_count = 0
    csv_path = os.path.join(directory, 'missing_matches.csv')

    for file_path in markdown_files:
        print(f"processing: {file_path.name}")

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        frontmatter, body = extract_frontmatter_and_content(content)

        # check if movie data already exists
        if has_movie_data(frontmatter):
            print(f"skipping: movie data already exists")
            skipped_count += 1
            continue

        title = extract_first_h1(body)

        if title:
            print(f"searching for: {title}")
            movie_data = search_omdb(title, api_key)

            if movie_data:
                print(f"found data, updating frontmatter")
                update_markdown_file(file_path, movie_data)
                processed_count += 1
            else:
                print(f"no data found for: {title}, adding to missing_matches.csv")
                add_to_missing_csv(file_path.name, title, csv_path)
                missing_count += 1
        else:
            print(f"no h1 heading found in {file_path.name}")

    print(f"\nsummary: {processed_count} files updated, {skipped_count} files skipped, {missing_count} missing matches")
    if missing_count > 0:
        print(f"check {csv_path} and add imdb ids, then run movie_fixer.py")


# usage
if __name__ == "__main__":
    API_KEY = os.getenv("OMDB_API_KEY")
    DIRECTORY = os.getenv("MARKDOWN_DIRECTORY", "./markdown_files")

    if not API_KEY:
        print("error: OMDB_API_KEY not found in environment variables")
        exit(1)

    process_markdown_files(DIRECTORY, API_KEY)