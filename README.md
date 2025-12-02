# Oliwka Translator

A warm single-page translator that focuses on Spanish/Russian → Polish. Paste words or bracketed phrases to get precise Polish translations, two example sentences with translations, and automatic grouping into nouns, verbs, adjectives, adverbs, or phrases. You can save entries to a database (PostgreSQL on Railway recommended; falls back to SQLite locally).

## Features
- Auto-detects Spanish or Russian input and translates to Polish using the free [LibreTranslate](https://libretranslate.de) service (no API key required by default).
- Handles lists of words and bracketed phrases; phrases stay together and everything else is translated individually.
- Produces two warm example sentences for each entry and translates them to Polish.
- Displays results grouped into five categories (nouns, verbs, adjectives, adverbs, phrases/other).
- Save any entry to the database and view saved words anytime.

## Quickstart
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the app:
   ```bash
   flask --app app run --host 0.0.0.0 --port 5000
   ```
   or `python app.py`.
3. Open `http://localhost:5000` and paste your words.

## Railway database
- Provision a PostgreSQL database on Railway and copy the connection string.
- Set the `DATABASE_URL` environment variable to that string (for example, `postgresql+psycopg2://user:pass@host:port/dbname`).
- Deploy the app to Railway; the table `word_entries` will be created automatically.
- The **Saved dictionary** panel reads directly from this database.

## Configuration
- `DATABASE_URL`: database connection string. Defaults to local SQLite file `translations.db`.
- `LIBRETRANSLATE_URL`: override the translation endpoint if you self-host LibreTranslate.
- `PORT`: port for the Flask server (defaults to `5000`).

## Notes
- Part-of-speech grouping uses lightweight heuristics for Russian and Spanish plus phrase detection. Bracketed items such as `(llegar a un acuerdo)` are kept intact and treated as phrases.
- LibreTranslate is free but public instances may enforce fair-use limits. For unlimited usage, point `LIBRETRANSLATE_URL` to your own LibreTranslate deployment.
