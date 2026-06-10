import re
import urllib.parse
from bs4 import BeautifulSoup
import httpx
from playwright.sync_api import sync_playwright
import time
import logging

# Set up logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Scraper")

def clean_text(text):
    if not text:
        return ""
    # Strip out Private Use Area (PUA) Unicode characters
    text = re.sub(r'[\uE000-\uF8FF]', '', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


class GoogleMapsScraper:
    def __init__(self, query, max_results=10, headless=True, progress_callback=None):
        self.query = query
        self.max_results = max_results
        self.headless = headless
        self.progress_callback = progress_callback
        self.client = httpx.Client(
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            timeout=8.0,
            follow_redirects=True,
            verify=False # Bypass SSL errors to maximize success
        )

    def log(self, message):
        logger.info(message)
        if self.progress_callback:
            self.progress_callback({"type": "log", "message": message})

    def send_data(self, data):
        if self.progress_callback:
            self.progress_callback({"type": "data", "data": data})

    def run(self):
        self.log(f"Starting search for: '{self.query}' (Max results: {self.max_results}, Headless: {self.headless})")
        
        place_urls = []
        
        try:
            with sync_playwright() as p:
                self.log("Launching browser...")
                browser = p.chromium.launch(
                    headless=self.headless, 
                    args=["--disable-blink-features=AutomationControlled"]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    viewport={"width": 1280, "height": 800}
                )
                page = context.new_page()
                
                # Navigate to Google Maps search
                search_url = f"https://www.google.com/maps/search/{urllib.parse.quote_plus(self.query)}"
                self.log(f"Navigating to: {search_url}")
                page.goto(search_url)
                
                # Check if we redirect directly to a single business page, or get a list
                try:
                    page.wait_for_selector('div[role="feed"], h1', timeout=15000)
                except Exception:
                    self.log("Timeout waiting for search results feed. No listings found.")
                    browser.close()
                    return []

                # Single business page redirect check
                if page.locator('div[role="feed"]').count() == 0 and page.locator('h1').count() > 0:
                    self.log("Redirected directly to a single business listing.")
                    current_url = page.url
                    place_urls.append(current_url)
                else:
                    self.log("Scrolling results feed to collect listing URLs...")
                    # Scroll results
                    last_count = 0
                    no_change_count = 0
                    
                    while len(place_urls) < self.max_results and no_change_count < 8:
                        # Find place links inside the feed
                        links = page.locator('div[role="feed"] a[href*="/maps/place/"]')
                        count = links.count()
                        
                        # Add new URLs
                        new_urls_found = 0
                        for i in range(count):
                            href = links.nth(i).get_attribute('href')
                            if href:
                                # Clean the URL (remove unnecessary query params to keep it clean)
                                clean_url = href.split('?')[0]
                                if clean_url not in place_urls:
                                    place_urls.append(clean_url)
                                    new_urls_found += 1
                                    if len(place_urls) >= self.max_results:
                                        break
                        
                        self.log(f"Scrolled and gathered {len(place_urls)} listing URLs...")
                        if len(place_urls) >= self.max_results:
                            break
                            
                        # Scroll feed container down
                        feed_el = page.locator('div[role="feed"]').first
                        if feed_el.count() > 0:
                            page.evaluate('(el) => el.scrollTop = el.scrollHeight', feed_el.element_handle())
                            page.wait_for_timeout(2000)
                        else:
                            break
                        
                        # Check progress
                        new_count = len(place_urls)
                        if new_count == last_count:
                            no_change_count += 1
                        else:
                            no_change_count = 0
                            last_count = new_count
                            
                    self.log(f"Finished gathering. Total unique listings found: {len(place_urls)}")

                # Now visit each listing and extract details
                results = []
                for index, url in enumerate(place_urls):
                    self.log(f"Extracting details for listing {index+1}/{len(place_urls)}...")
                    try:
                        details = self.extract_listing_details(page, url)
                        
                        # If website is present, crawl it for emails and owner info
                        if details.get("website"):
                            self.log(f"Crawling website: {details['website']}...")
                            crawl_results = self.crawl_website(details["website"])
                            details.update(crawl_results)
                        else:
                            self.log("No website found for this business.")
                            details.update({
                                "website_status": "No website",
                                "emails": [],
                                "facebook": "",
                                "instagram": "",
                                "linkedin": "",
                                "twitter": "",
                                "owner_name": ""
                            })
                            
                        self.log(f"Successfully scraped: {details['name']}")
                        results.append(details)
                        self.send_data(details)
                        
                    except Exception as ex:
                        self.log(f"Error scraping listing {url}: {ex}")
                        
                browser.close()
                self.log(f"Scrape completed successfully. Total listings processed: {len(results)}")
                return results
                
        except Exception as e:
            self.log(f"Global scraper error: {e}")
            return []

    def extract_listing_details(self, page, url):
        page.goto(url)
        # Wait for either heading or body to load
        page.wait_for_selector('h1', timeout=12000)
        
        # 1. Business Name
        name = ""
        h1_el = page.locator('h1').first
        if h1_el.count() > 0:
            name = h1_el.inner_text().strip()
            
        # 2. Address
        address = ""
        addr_btn = page.locator('button[data-item-id="address"]').first
        if addr_btn.count() > 0:
            address = addr_btn.inner_text().strip()
        else:
            addr_aria = page.locator('button[aria-label*="Address"], button[aria-label*="address"]').first
            if addr_aria.count() > 0:
                address = addr_aria.inner_text().strip()

        # 3. Phone
        phone = ""
        phone_btn = page.locator('button[data-item-id^="phone:tel:"]').first
        if phone_btn.count() > 0:
            phone = phone_btn.inner_text().strip()
        else:
            phone_aria = page.locator('button[aria-label*="Phone"], button[aria-label*="phone"]').first
            if phone_aria.count() > 0:
                phone = phone_aria.inner_text().strip()

        # 4. Website
        website = ""
        web_link = page.locator('a[data-item-id="authority"]').first
        if web_link.count() > 0:
            website = web_link.get_attribute('href')
        else:
            web_aria = page.locator('a[aria-label*="Website"], a[aria-label*="website"]').first
            if web_aria.count() > 0:
                website = web_aria.get_attribute('href')
                
        if website:
            # Clean redirects
            if "google.com/url" in website:
                try:
                    parsed = urllib.parse.urlparse(website)
                    q_params = urllib.parse.parse_qs(parsed.query)
                    if 'q' in q_params:
                        website = q_params['q'][0]
                except Exception:
                    pass
            website = website.strip()

        # 5. Rating & Reviews
        rating = ""
        reviews_count = ""
        rating_container = page.locator('div.F7nice').first
        if rating_container.count() > 0:
            text = rating_container.inner_text()
            parts = [p.strip() for p in text.split() if p.strip()]
            if parts:
                rating = parts[0]
                if len(parts) > 1:
                    reviews_count = parts[1].replace('(', '').replace(')', '')
        else:
            stars_el = page.locator('span[aria-label*="stars"]').first
            if stars_el.count() > 0:
                aria_label = stars_el.get_attribute('aria-label') or ""
                match = re.search(r'(\d\.\d|\d)', aria_label)
                if match:
                    rating = match.group(1)
                
                rev_el = page.locator('span[aria-label*="reviews"]').first
                if rev_el.count() > 0:
                    rev_aria = rev_el.get_attribute('aria-label') or ""
                    match_rev = re.search(r'(\d+)', rev_aria)
                    if match_rev:
                        reviews_count = match_rev.group(1)

        return {
            "name": clean_text(name),
            "address": clean_text(address),
            "phone": clean_text(phone),
            "website": website,
            "rating": clean_text(rating),
            "reviews_count": clean_text(reviews_count),
            "maps_url": url
        }

    def crawl_website(self, site_url):
        results = {
            "website_status": "Accessible",
            "emails": [],
            "facebook": "",
            "instagram": "",
            "linkedin": "",
            "twitter": "",
            "owner_name": ""
        }
        
        # Standardize URL
        site_url = site_url.strip()
        if not site_url.startswith(('http://', 'https://')):
            site_url = 'https://' + site_url
            
        try:
            r = self.client.get(site_url)
            html = r.text
            soup = BeautifulSoup(html, 'html.parser')
        except Exception as e:
            self.log(f"Failed to access homepage {site_url}: {e}")
            results["website_status"] = "Inaccessible/Error"
            return results
            
        # Parse homepage
        emails = self.extract_emails_from_text(html)
        socials = self.extract_socials_from_soup(soup)
        owner = self.extract_owner_from_text(soup.get_text())
        
        results["emails"].extend(emails)
        results.update(socials)
        if owner:
            results["owner_name"] = owner
            
        # Find internal links to contact/about pages
        internal_links = []
        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            # Check for matches
            lower_href = href.lower()
            if any(k in lower_href for k in ['about', 'contact', 'team', 'staff', 'owner', 'founder']):
                # Resolve relative URL
                full_url = urllib.parse.urljoin(site_url, href)
                # Keep it internal to the same domain
                if urllib.parse.urlparse(full_url).netloc == urllib.parse.urlparse(site_url).netloc:
                    if full_url not in internal_links and full_url != site_url:
                        internal_links.append(full_url)
                        
        # Visit up to 2 internal links to search for emails and owners
        links_to_crawl = internal_links[:2]
        for link in links_to_crawl:
            self.log(f"Crawling subpage: {link}...")
            try:
                sub_r = self.client.get(link)
                sub_html = sub_r.text
                sub_soup = BeautifulSoup(sub_html, 'html.parser')
                
                sub_emails = self.extract_emails_from_text(sub_html)
                results["emails"].extend(sub_emails)
                
                # Check for socials if not found yet
                sub_socials = self.extract_socials_from_soup(sub_soup)
                for platform, value in sub_socials.items():
                    if value and not results[platform]:
                        results[platform] = value
                        
                # Check for owner name if not found yet
                if not results["owner_name"]:
                    sub_owner = self.extract_owner_from_text(sub_soup.get_text())
                    if sub_owner:
                        results["owner_name"] = sub_owner
            except Exception as e:
                self.log(f"Error crawling subpage {link}: {e}")
                
        # Post-process results
        results["emails"] = list(set(results["emails"]))
        return results

    def extract_emails_from_text(self, text):
        email_regex = re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b')
        emails = email_regex.findall(text)
        valid_emails = []
        for email in emails:
            email = email.lower().strip()
            # Exclude common false positives, static image formats, and sample addresses
            if not any(email.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.pdf', '.css', '.js']):
                if not any(domain in email for domain in ['example.com', 'yourdomain.com', 'email.com', 'domain.com', 'sentry.io']):
                    valid_emails.append(email)
        return list(set(valid_emails))

    def extract_socials_from_soup(self, soup):
        socials = {
            "facebook": "",
            "instagram": "",
            "linkedin": "",
            "twitter": ""
        }
        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            lower_href = href.lower()
            if "facebook.com/" in lower_href and not socials["facebook"]:
                # Filter out sharing links
                if "sharer" not in lower_href:
                    socials["facebook"] = href
            elif "instagram.com/" in lower_href and not socials["instagram"]:
                socials["instagram"] = href
            elif "linkedin.com/" in lower_href and not socials["linkedin"]:
                # Prefer company pages or personal profiles over shares
                if "sharearticle" not in lower_href:
                    socials["linkedin"] = href
            elif ("twitter.com/" in lower_href or "x.com/" in lower_href) and not socials["twitter"]:
                if "intent/" not in lower_href and "share" not in lower_href:
                    socials["twitter"] = href
        return socials

    def extract_owner_from_text(self, text):
        # Normalize text spacing
        text = re.sub(r'\s+', ' ', text)
        
        # Patterns for name extraction
        # Pattern 1: Role keyword followed by name, allowing symbols like ':' or '-'
        # Example: "Founder: John Doe", "CEO - Jane Smith"
        # Since we use Capitalized Words for names, the regex looks for capital letters.
        p1 = re.compile(
            r'\b(?:owner|founder|ceo|president|co-founder|founder and owner|owner and founder)\s*(?::|is|–|-|—)?\s*([A-Z][a-zA-Z\-\.]+(?:\s+[A-Z][a-zA-Z\-\.]+){1,2})',
            re.IGNORECASE
        )
        
        # Pattern 2: Founded/owned by followed by name
        # Example: "founded by Arthur Pendragon"
        p2 = re.compile(
            r'\b(?:founded|owned|created)\s+by\s+([A-Z][a-zA-Z\-\.]+(?:\s+[A-Z][a-zA-Z\-\.]+){1,2})',
            re.IGNORECASE
        )
        
        # Pattern 3: Name followed by role
        # Example: "John Doe, Founder & CEO"
        p3 = re.compile(
            r'\b([A-Z][a-zA-Z\-\.]+(?:\s+[A-Z][a-zA-Z\-\.]+){1,2})\s*[\(,\-—–]\s*(?:owner|founder|ceo|president|co-founder)\b',
            re.IGNORECASE
        )
        
        # Search using heuristics
        for p in [p1, p2, p3]:
            matches = p.findall(text)
            for match in matches:
                name = match.strip()
                # Clean up ending punctuation
                name = re.sub(r'[\.\,\:\-\s]+$', '', name)
                
                # Check for common stop words that could look like names (due to capitalization)
                stop_words = {"Our", "We", "The", "In", "On", "At", "By", "For", "To", "With", "About", "Contact", "Meet", "Welcome", "Hello", "Get", "Join", "Check", "How", "Why", "Company", "Services"}
                words = name.split()
                if words and not any(w in stop_words for w in words):
                    # Ensure name has at least a first and last name (at least 2 words)
                    if len(words) >= 2:
                        return name
        return ""
