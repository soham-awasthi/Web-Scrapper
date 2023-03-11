# Instagram Scraper

## Prerequisites

1. Install Python 3.x on your system.
2. Install dependencies using:
   ```sh
   pip install selenium webdriver-manager python-dotenv
   ```
   OR
   ```sh
   pip install -r ./requirements.txt
   ```

## Steps to Execute

1. Copy the script into a Python file (e.g., `instagram_scraper.py`).
2. Update Instagram credentials in `.env`:
   ```sh
   INSTAGRAM_USERNAME=your_username
   INSTAGRAM_PASSWORD=your_password
   ```
3. Add Instagram profile URLs to the `profile_urls` list.
4. Run the script:
   ```sh
   python instagram_scraper.py
   ```
5. After execution, the output will be available in:
   ```sh
   instagram_data.csv
   ```

---

# Discord Scraper

## Prerequisites

1. Install Python 3.x on your system.
2. Install dependencies:
   ```sh
   pip install selenium webdriver-manager python-dotenv
   ```
   OR
   ```sh
   pip install -r ./requirements.txt
   ```

## Steps to Execute

### Set up credentials in a `.env` file:

```sh
DISCORD_EMAIL=your_email
DISCORD_PASSWORD=your_password
```

1. Add Discord Server URLs in the `server_urls` list.
2. Add Channel URLs in the `channel_urls` list.
3. Run the script:
   ```sh
   python discord_scraper.py
   ```
4. The extracted data will be saved in:
   ```sh
   discord_data.json
   ```


