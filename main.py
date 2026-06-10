import sys
import asyncio

# Force Windows asyncio event loop policy to support subprocesses (needed by Playwright)
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import json
import queue
import threading
import csv
import io
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from scraper import GoogleMapsScraper
import os

app = FastAPI(title="Google Maps Scraper Dashboard")

# In-memory storage for the current session's scraped data
scraped_data_store = []
store_lock = threading.Lock()

# Auto-create the static directory if it doesn't exist
os.makedirs("static", exist_ok=True)

@app.get("/api/scrape")
def scrape_endpoint(
    q: str = Query(..., description="The search query"),
    max_results: int = Query(10, description="Max results to scrape"),
    headless: bool = Query(True, description="Run browser in headless mode")
):
    """
    Triggers the scraper in a background thread and streams progress logs
    and results in real-time using Server-Sent Events (SSE).
    """
    event_queue = queue.Queue()

    def progress_callback(event):
        event_queue.put(event)

    def run_scraper_thread():
        global scraped_data_store
        
        # Reset local data store
        with store_lock:
            scraped_data_store = []

        try:
            scraper = GoogleMapsScraper(
                query=q,
                max_results=max_results,
                headless=headless,
                progress_callback=progress_callback
            )
            results = scraper.run()
            
            # Save results in-memory
            with store_lock:
                scraped_data_store = results
            
            # Save to a local CSV file in the workspace automatically
            csv_filepath = "scraped_businesses.csv"
            save_data_to_csv(results, csv_filepath)
            
            event_queue.put({
                "type": "done",
                "message": f"Successfully scraped {len(results)} listings. Saved to {csv_filepath}.",
                "total": len(results)
            })
        except Exception as e:
            event_queue.put({
                "type": "error",
                "message": f"An error occurred: {str(e)}"
            })
        finally:
            # Sentinel to close stream
            event_queue.put(None)

    # Start the scraper in a separate daemon thread
    threading.Thread(target=run_scraper_thread, daemon=True).start()

    def event_generator():
        while True:
            event = event_queue.get()
            if event is None:
                break
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/download")
def download_csv():
    """
    Generates and returns a CSV file of the current session's scraped data.
    """
    global scraped_data_store
    with store_lock:
        if not scraped_data_store:
            raise HTTPException(status_code=400, detail="No data available to download. Please run a scrape session first.")
        
        data = list(scraped_data_store)

    # Write CSV to a string buffer
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header
    writer.writerow([
        "Name", "Address", "Phone", "Website", "Rating", "Reviews Count",
        "Emails", "Facebook", "Instagram", "LinkedIn", "Twitter/X",
        "Owner Name", "Website Status", "Google Maps URL"
    ])
    
    # Rows
    for item in data:
        # Join emails into a comma-separated string
        emails_str = ", ".join(item.get("emails", []))
        
        writer.writerow([
            item.get("name", ""),
            item.get("address", ""),
            item.get("phone", ""),
            item.get("website", ""),
            item.get("rating", ""),
            item.get("reviews_count", ""),
            emails_str,
            item.get("facebook", ""),
            item.get("instagram", ""),
            item.get("linkedin", ""),
            item.get("twitter", ""),
            item.get("owner_name", ""),
            item.get("website_status", ""),
            item.get("maps_url", "")
        ])

    output.seek(0)
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=scraped_leads.csv"}
    )


def save_data_to_csv(data, filepath):
    """
    Helper to save scraped data directly to a local file.
    """
    try:
        with open(filepath, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Name", "Address", "Phone", "Website", "Rating", "Reviews Count",
                "Emails", "Facebook", "Instagram", "LinkedIn", "Twitter/X",
                "Owner Name", "Website Status", "Google Maps URL"
            ])
            for item in data:
                emails_str = ", ".join(item.get("emails", []))
                writer.writerow([
                    item.get("name", ""),
                    item.get("address", ""),
                    item.get("phone", ""),
                    item.get("website", ""),
                    item.get("rating", ""),
                    item.get("reviews_count", ""),
                    emails_str,
                    item.get("facebook", ""),
                    item.get("instagram", ""),
                    item.get("linkedin", ""),
                    item.get("twitter", ""),
                    item.get("owner_name", ""),
                    item.get("website_status", ""),
                    item.get("maps_url", "")
                ])
    except Exception as e:
        print(f"Error saving auto CSV: {e}")


# Serve static frontend files
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    # Start the server on port 8005
    # On Windows, we run with reload=False and loop="asyncio" to avoid asyncio conflicts with Playwright.
    loop_type = "asyncio" if sys.platform.startswith("win") else "auto"
    uvicorn.run("main:app", host="127.0.0.1", port=8005, reload=False, loop=loop_type)
