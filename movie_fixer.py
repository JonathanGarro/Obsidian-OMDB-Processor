import os
import re
import requests
import yaml
import csv
from pathlib import Path
from dotenv import load_dotenv

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


def get_omdb_by_id(imdb_id, api_key):
    """fetch movie data from omdb api using imdb id"""
    url = f"http://www.omdbapi.com/?i={imdb_id}&apikey={api_key}"
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
        # convert rating to percentage
        my_rating_percent = float(rating) * 10

        # parse rotten tomatoes score (remove % and convert to int)
        rt_score = int(rotten_tomatoes.rstrip('%'))

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


def process_missing_matches(csv_path, directory, api_key):
    """process movies from missing_matches.csv using manually added imdb ids"""
    if not os.path.exists(csv_path):
        print(f"error: {csv_path} not found")
        return

    processed_count = 0
    skipped_count = 0
    error_count = 0

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            filename = row['filename']
            imdb_id = row['imdb_id'].strip()

            if not imdb_id:
                print(f"skipping {filename}: no imdb id provided")
                skipped_count += 1
                continue

            file_path = os.path.join(directory, filename)

            if not os.path.exists(file_path):
                print(f"error: {filename} not found in directory")
                error_count += 1
                continue

            print(f"processing: {filename} with imdb id: {imdb_id}")
            movie_data = get_omdb_by_id(imdb_id, api_key)

            if movie_data:
                print(f"found data, updating frontmatter")
                update_markdown_file(file_path, movie_data)
                processed_count += 1
            else:
                print(f"error: could not fetch data for imdb id: {imdb_id}")
                error_count += 1

    print(f"\nsummary: {processed_count} files updated, {skipped_count} skipped, {error_count} errors")

    if processed_count > 0:
        # optionally delete or rename the csv file after processing
        print(f"\nto process these files again, keep {csv_path}")
        print(f"to start fresh, delete or rename {csv_path}")


# usage
if __name__ == "__main__":
    API_KEY = os.getenv("OMDB_API_KEY")
    DIRECTORY = os.getenv("MARKDOWN_DIRECTORY", "./markdown_files")
    CSV_PATH = os.path.join(DIRECTORY, "missing_matches.csv")

    if not API_KEY:
        print("error: OMDB_API_KEY not found in environment variables")
        exit(1)

    process_missing_matches(CSV_PATH, DIRECTORY, API_KEY)