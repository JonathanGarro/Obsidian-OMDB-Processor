# OMDB Movie Lookup

Simple utility that helps me manage IMDB data for personal movie reviews in Obsidian. It:

1. Scans markdown files in my movie review folder
2. Extracts movie titles from the first H1 heading
3. Fetches movie data from the OMDB API
4. Adds the data to the YAML frontmatter

## Features

- Automatically adds IMDB ratings, votes, Metascore, and Rotten Tomatoes scores
- Creates links to IMDB pages for that movie
- Calculates the delta between my personal rating and Rotten Tomatoes score
- Handles missing matches with a manual correction workflow

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/omdb-movie-lookup.git
   cd omdb-movie-lookup
   ```

2. Install required dependencies:
   ```
   pip install requests pyyaml python-dotenv
   ```

3. Get an API key from [OMDB API](http://www.omdbapi.com/)

4. Create a `.env` file in the project root with the following variables:
   ```
   OMDB_API_KEY=your_api_key_here
   MARKDOWN_DIRECTORY=/path/to/your/markdown/files
   ```

## Usage

### Expected Markdown Format

Markdown files should have YAML frontmatter and an H1 heading with the movie title:

```markdown
---
date: 2023-01-01
rating: 8.5
tags: [drama, sci-fi]
---

# Interstellar

Movie review or notes here...
```

### Processing Files

1. **Initial Processing**

   Run the main processor to add movie data to all markdown files:

   ```
   python movie_processor.py
   ```

   This will:
   - Process all .md files in your specified directory
   - Add movie data to the frontmatter
   - Create a `missing_matches.csv` file for any movies that couldn't be found

2. **Fixing Missing Matches**

   If some movies weren't found automatically:
   
   1. Open the `missing_matches.csv` file
   2. Add the correct IMDB ID for each movie in the `imdb_id` column (get this by finding the page in the browser and grabbing the ID from the URL)
   3. Run the fixer script:
      ```
      python movie_fixer.py
      ```

### After Processing

Your markdown files will be updated with additional frontmatter:

```markdown
---
date: 2023-01-01
rating: 8.5
tags: [drama, sci-fi]
imdb_id: tt0816692
imdb_link: "[Interstellar on IMDB](https://www.imdb.com/title/tt0816692/)"
imdb_rating: 8.6
imdb_votes: 1,700,000
metascore: 74
rotten_tomatoes: 73%
my_rating_delta: 12
---

# Interstellar

Murph!!!
```

## Environment Variables

- `OMDB_API_KEY`: API key for the OMDB API (required)
- `MARKDOWN_DIRECTORY`: Path to the directory containing your markdown files (required)
