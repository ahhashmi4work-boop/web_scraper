from flask import Flask, render_template
import pandas as pd
import requests
import re
from bs4 import BeautifulSoup
import urllib3
import os

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# ===== EMAIL SCRAPER FUNCTION =====
def scrape_emails(url):
    """Scrape emails from a given URL"""
    if pd.isna(url) or str(url).strip() == "":
        return "Empty URL"

    url = str(url).strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        )
    }

    pages_to_try = [
        url,
        url + "/contact",
        url + "/contact-us",
        url + "/about",
        url + "/about-us"
    ]

    emails_found = set()

    for page in pages_to_try:
        try:
            response = requests.get(page, headers=headers, timeout=15, verify=False)
            if response.status_code != 200:
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            
            # Extract emails from mailto links
            for link in soup.find_all('a', href=re.compile(r'^mailto:', re.I)):
                email = re.sub(r'mailto:', '', link.get('href', ''), flags=re.I).split('?')[0]
                if email.strip():
                    emails_found.add(email.strip())
            
            # Extract emails from text content
            text = soup.get_text(separator=" ")
            emails = re.findall(
                r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text
            )
            emails_found.update(emails)
        except requests.exceptions.RequestException:
            continue
        except Exception as e:
            print(f"Error processing {page}: {e}")
            continue

    return ", ".join(sorted(emails_found)) if emails_found else "No emails found"

# ===== ROUTE =====
@app.route("/")
def index():
    """Main route that reads CSV, scrapes emails, and displays results"""
    input_file = "web scrapper.csv"

    if not os.path.exists(input_file):
        return render_template("index.html", 
                             error=f"File not found: {input_file}",
                             data=[])

    try:
        # Try tab-separated first (as the file seems to be), then comma-separated
        try:
            df = pd.read_csv(input_file, sep="\t")
        except:
            df = pd.read_csv(input_file, sep=",")
    except Exception as e:
        return render_template("index.html",
                             error=f"Error reading CSV: {str(e)}",
                             data=[])

    # Normalize column names
    df.columns = df.columns.str.strip().str.lower()
    
    # Find URL column (could be 'url', 'urls', 'website', etc.)
    url_column = None
    for col in ['urls', 'url', 'website', 'link']:
        if col in df.columns:
            url_column = col
            break
    
    if not url_column:
        return render_template("index.html",
                             error=f"URL column not found. Available columns: {df.columns.tolist()}",
                             data=[])

    # Only scrape emails for rows that don't already have emails
    if 'emails' not in df.columns:
        df['emails'] = ''
    
    # Scrape emails for rows with empty email fields
    mask = df['emails'].isna() | (df['emails'].astype(str).str.strip() == '')
    df.loc[mask, 'emails'] = df.loc[mask, url_column].apply(scrape_emails)

    # Save output file
    try:
        df.to_csv("output.csv", index=False)
    except Exception as e:
        print(f"Warning: Could not save output.csv: {e}")

    # Convert dataframe to list of dicts for template
    data = df.to_dict(orient="records")

    return render_template("index.html", data=data, error=None)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)
