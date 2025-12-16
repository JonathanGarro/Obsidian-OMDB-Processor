import os
import re
import requests
import yaml
import csv
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

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
        frontmatter['imdb_link'] = f"https://www.imdb.com/title/{imdb_id}/" if imdb_id else None
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


def add_to_letterboxd_csv(frontmatter, body, csv_path):
    """add film rating to letterboxd import csv"""
    # only process if there's an imdb_id and rating
    imdb_id = frontmatter.get('imdb_id')
    rating = frontmatter.get('rating')

    if not imdb_id or not rating:
        return False

    # convert rating from 0-5 scale to letterboxd's 0.5-5.0 scale (in 0.5 increments)
    try:
        letterboxd_rating = float(rating)
    except (ValueError, TypeError):
        return False

    # get watched date from finished_on field, fallback to date field, then current date
    watched_date = frontmatter.get('finished_on') or frontmatter.get('date')

    if watched_date:
        if isinstance(watched_date, datetime):
            watched_date = watched_date.strftime('%Y-%m-%d')
        else:
            # if it's already a string, use as-is
            watched_date = str(watched_date)
    else:
        # only use current date if no date field exists at all
        watched_date = datetime.now().strftime('%Y-%m-%d')

    # get review text (first paragraph after h1, or full body)
    review = body.strip().split('\n\n')[0] if body.strip() else ''
    review = review[:500]  # letterboxd has character limits

    # check if file exists to determine if we need headers
    file_exists = os.path.isfile(csv_path)

    with open(csv_path, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            # letterboxd csv format headers
            writer.writerow(['imdbID', 'Rating', 'WatchedDate', 'Review'])
        writer.writerow([imdb_id, letterboxd_rating, watched_date, review])

    return True


def process_markdown_files(directory, api_key):
    """process all markdown files in directory"""
    markdown_files = Path(directory).glob('*.md')

    processed_count = 0
    skipped_count = 0
    missing_count = 0
    letterboxd_count = 0
    
    missing_csv_path = os.path.join(directory, 'missing_matches.csv')
    letterboxd_csv_path = os.path.join('outputs', 'letterboxd_import.csv')
    
    # create outputs directory if it doesn't exist
    os.makedirs('outputs', exist_ok=True)
    
    # remove existing letterboxd csv to start fresh
    if os.path.exists(letterboxd_csv_path):
        os.remove(letterboxd_csv_path)

    for file_path in markdown_files:
        print(f"processing: {file_path.name}")

        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        frontmatter, body = extract_frontmatter_and_content(content)

        # check if movie data already exists
        if has_movie_data(frontmatter):
            print(f"skipping omdb lookup: movie data already exists")
            skipped_count += 1
            
            # still add to letterboxd csv if we have the data
            if add_to_letterboxd_csv(frontmatter, body, letterboxd_csv_path):
                letterboxd_count += 1
                print(f"added to letterboxd import csv")
            continue

        title = extract_first_h1(body)

        if title:
            print(f"searching for: {title}")
            movie_data = search_omdb(title, api_key)

            if movie_data:
                print(f"found data, updating frontmatter")
                update_markdown_file(file_path, movie_data)
                processed_count += 1
                
                # re-read file to get updated frontmatter for letterboxd export
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                frontmatter, body = extract_frontmatter_and_content(content)
                
                if add_to_letterboxd_csv(frontmatter, body, letterboxd_csv_path):
                    letterboxd_count += 1
                    print(f"added to letterboxd import csv")
            else:
                print(f"no data found for: {title}, adding to missing_matches.csv")
                add_to_missing_csv(file_path.name, title, missing_csv_path)
                missing_count += 1
        else:
            print(f"no h1 heading found in {file_path.name}")

    print(f"\nsummary:")
    print(f"  {processed_count} files updated with omdb data")
    print(f"  {skipped_count} files skipped (already had data)")
    print(f"  {missing_count} missing matches")
    print(f"  {letterboxd_count} films added to letterboxd import")
    
    if missing_count > 0:
        print(f"\ncheck {missing_csv_path} and add imdb ids, then run movie_fixer.py")
    
    if letterboxd_count > 0:
        print(f"\nimport {letterboxd_csv_path} to letterboxd:")
        print(f"  1. go to https://letterboxd.com/import/")
        print(f"  2. upload the csv file")
        print(f"  3. follow the import wizard")


# usage
if __name__ == "__main__":
    API_KEY = os.getenv("OMDB_API_KEY")
    DIRECTORY = os.getenv("MARKDOWN_DIRECTORY", "./markdown_files")

    if not API_KEY:
        print("error: OMDB_API_KEY not found in environment variables")
        exit(1)

    process_markdown_files(DIRECTORY, API_KEY)