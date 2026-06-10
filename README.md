# 🗺️ Google Maps Scraper Pro

A powerful, local lead-generation tool that scrapes Google Maps business listings and automatically crawls their websites to extract contact details — emails, phone numbers, social media links, and owner names. Results stream live to a sleek dark-mode dashboard and export to CSV with one click.

---

## ✨ Features

| Feature | Details |
|---|---|
| **Google Maps Scraping** | Searches any category + location (e.g. *"Dentists in New York"*) and extracts business name, address, phone, rating, reviews count, website URL, and Maps link. |
| **Website Crawling** | Automatically visits each business's website plus internal pages (`/about`, `/contact`, `/team`) to find emails, social profiles, and owner/founder names. |
| **Live Dashboard** | Real-time stat cards, scrolling data table, and a terminal-style log console — all updating as the scraper runs. |
| **CSV Export** | Download a structured CSV of all scraped leads, or find the auto-saved `scraped_businesses.csv` in the project folder. |
| **Headless Toggle** | Run the browser invisibly in the background, or watch it scroll through Google Maps live. |
| **Configurable Results** | Set exactly how many listings you need (1–200). |

---

## 🛠️ Tech Stack

- **Backend:** Python 3.10+, FastAPI, Uvicorn
- **Browser Automation:** Playwright (Chromium)
- **Web Crawling:** HTTPX, BeautifulSoup4
- **Frontend:** Vanilla HTML / CSS / JavaScript (no frameworks)
- **Data Streaming:** Server-Sent Events (SSE)

---

## 📁 Project Structure

```
Demo Website/
├── main.py              # FastAPI server — API routes, SSE streaming, CSV export
├── scraper.py           # Core scraper engine — Playwright + website crawler
├── requirements.txt     # Python dependencies
├── scraped_businesses.csv  # Auto-generated CSV output (after first scrape)
└── static/
    ├── index.html       # Dashboard UI
    ├── style.css        # Dark-mode styling, animations
    └── app.js           # Frontend logic — SSE handling, table updates
```

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.10+** installed and available on PATH
- **Windows / macOS / Linux** (tested on Windows)

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright Browser

```bash
python -m playwright install chromium
```

This downloads a local copy of Chromium (~136 MB). Only needed once.

### 3. Start the Server

```bash
python main.py
```

You should see:

```
INFO:     Uvicorn running on http://127.0.0.1:8005 (Press CTRL+C to quit)
INFO:     Application startup complete.
```

### 4. Open the Dashboard

Navigate to **[http://localhost:8005](http://localhost:8005)** in your browser.

---

## 📖 Usage

1. **Search Query** — Enter a category and location (e.g. `Coffee Shops in Seattle`, `Plumbers in Chicago`).
2. **Max Results** — Set the number of listings to scrape (1–200).
3. **Headless Toggle** — Check to run invisibly; uncheck to watch the browser scroll Google Maps live.
4. **Start Scraper** — Click to begin. Watch progress in the live log console and results appear in the table.
5. **Download CSV** — Once complete, click the green button to download your leads as a CSV file.

### Extracted Data Fields

| Field | Source |
|---|---|
| Business Name | Google Maps |
| Address | Google Maps |
| Phone Number | Google Maps |
| Rating & Reviews Count | Google Maps |
| Website URL | Google Maps |
| Google Maps Link | Google Maps |
| Email Address(es) | Website crawl |
| Facebook | Website crawl |
| Instagram | Website crawl |
| LinkedIn | Website crawl |
| Twitter / X | Website crawl |
| Owner / Founder Name | Website crawl (heuristic) |

---

## ⚠️ Important Notes

- **Rate Limiting:** The scraper uses natural delays between requests. Avoid setting extremely high result counts to prevent temporary blocks from Google.
- **Owner Name Detection:** Owner/founder names are extracted using keyword heuristics (e.g. *"Founded by..."*, *"CEO: ..."*). Not all websites publish this information, so this field may be blank.
- **Terms of Service:** Scraping Google Maps may violate Google's Terms of Service. Use this tool responsibly and only for publicly available business data.
- **Port Conflict:** If port `8005` is already in use, edit the port number at the bottom of `main.py`.

---

## 🛑 Stopping the Server

Press `Ctrl+C` in the terminal where `python main.py` is running.

---

## 📄 License

This project is for personal and educational use.
