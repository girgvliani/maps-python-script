import requests
import csv
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium_stealth import stealth
import random
import re

# Your Google Places API key
API_KEY = "AIzaSyD9cHRbxFWylqVNy_FgrYJxNloPv7ZuoIg"

# Search keywords
KEYWORDS = ["Hotel", "Resort", "Hostel", "Bungalow", "Guesthouse", "Villas"]

# Koh Pha Ngan coordinates
LOCATION = "9.7367,100.0264"
RADIUS = 15000

# GEL to USD conversion rate (approximate)
GEL_TO_USD = 2.7

def setup_driver():
    """Setup Chrome driver with maximum human-like behavior"""
    options = Options()
    
    # Comment out headless for testing, uncomment for production
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--start-maximized")
    options.add_argument("--window-size=1920,1080")
    
    # Real user agent
    options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Remove automation indicators
    options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
    options.add_experimental_option('useAutomationExtension', False)
    
    prefs = {
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
        "profile.default_content_setting_values.notifications": 2
    }
    options.add_experimental_option("prefs", prefs)
    
    driver = webdriver.Chrome(options=options)
    
    # Apply stealth
    stealth(driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="Win32",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )
    
    return driver

def human_delay(min_seconds=2, max_seconds=5):
    """Random delay to mimic human"""
    time.sleep(random.uniform(min_seconds, max_seconds))

def human_scroll(driver):
    """Scroll like a real human - slow and random"""
    try:
        scrolls = random.randint(2, 4)
        for i in range(scrolls):
            scroll_amount = random.randint(200, 500)
            driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            time.sleep(random.uniform(0.5, 1.5))
    except:
        pass

def search_places_nearby(keyword):
    """Search for places using Nearby Search API"""
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    
    params = {
        "location": LOCATION,
        "radius": RADIUS,
        "keyword": keyword,
        "type": "lodging",
        "key": API_KEY
    }
    
    all_results = []
    
    while True:
        response = requests.get(url, params=params)
        data = response.json()
        
        if data.get("status") not in ["OK", "ZERO_RESULTS"]:
            print(f"  Search status: {data.get('status')}")
            break
        
        if data.get("status") == "OK":
            all_results.extend(data.get("results", []))
        
        next_page_token = data.get("next_page_token")
        if not next_page_token:
            break
            
        time.sleep(2)
        params = {"pagetoken": next_page_token, "key": API_KEY}
    
    return all_results

def get_place_details(place_id):
    """Get place details from API"""
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    
    params = {
        "place_id": place_id,
        "fields": "name,formatted_address,geometry,url,business_status,rating,user_ratings_total,price_level,website,international_phone_number,types,reservable,photos",
        "key": API_KEY
    }
    
    response = requests.get(url, params=params)
    data = response.json()
    
    if data.get("status") == "OK":
        return data.get("result", {})
    return {}

def scrape_google_maps_prices_and_photos(driver, google_maps_url, hotel_name):
    """Scrape prices and photos from Google Maps HTML like a human"""
    try:
        print(f"  Opening Google Maps...")
        driver.get(google_maps_url)
        
        # Wait like a human reading the page
        human_delay(6, 9)
        
        scraped_data = {
            "min_price_usd": "N/A",
            "total_photos": 0,
            "price_level_scraped": ""
        }
        
        # Human-like scrolling
        print(f"  Reading page content...")
        human_scroll(driver)
        human_delay(2, 3)
        
        # Get page HTML and text
        page_source = driver.page_source
        page_text = driver.find_element(By.TAG_NAME, "body").text
        
        # === EXTRACT PRICE FROM GEORGIAN TEXT "მეტი ფასი XXX ₾" ===
        print(f"  Looking for prices...")
        
        # Method 1: Look for Georgian "მეტი ფასი XXX ₾" (More prices from XXX ₾)
        georgian_pattern = r'მეტი ფასი\s+(\d+)\s*₾'
        match = re.search(georgian_pattern, page_text)
        
        if match:
            lari_price = int(match.group(1))
            usd_price = int(lari_price / GEL_TO_USD)
            scraped_data["min_price_usd"] = f"${usd_price}"
            print(f"  ✓ Found price (Georgian): {lari_price} ₾ → ${usd_price} USD")
        else:
            # Method 2: Look for any price with ₾ symbol
            lari_matches = re.findall(r'(\d+)\s*₾', page_text)
            if lari_matches:
                # Filter valid hotel prices (100-10000 Lari)
                valid_prices = [int(p) for p in lari_matches if 100 < int(p) < 10000]
                if valid_prices:
                    min_lari = min(valid_prices)
                    min_usd = int(min_lari / GEL_TO_USD)
                    scraped_data["min_price_usd"] = f"${min_usd}"
                    print(f"  ✓ Found price (₾ symbol): {min_lari} ₾ → ${min_usd} USD")
            else:
                # Method 3: Look for GEL currency code
                gel_matches = re.findall(r'(\d+)\s*GEL', page_text)
                if gel_matches:
                    valid_gel = [int(p) for p in gel_matches if 100 < int(p) < 10000]
                    if valid_gel:
                        min_gel = min(valid_gel)
                        min_usd = int(min_gel / GEL_TO_USD)
                        scraped_data["min_price_usd"] = f"${min_usd}"
                        print(f"  ✓ Found price (GEL): {min_gel} GEL → ${min_usd} USD")
        
        if scraped_data["min_price_usd"] == "N/A":
            print(f"  ✗ No prices found")
        
        # === EXTRACT PHOTO COUNT ===
        print(f"  Looking for photos...")
        
        try:
            # Step 1: Find and click the first image/photo thumbnail on the page
            print(f"    Trying to click on photo thumbnail...")
            
            # Look for image elements (multiple possible selectors)
            photo_selectors = [
                "button[aria-label*='Photo']",
                "button[aria-label*='photo']",
                "button[jsaction*='photo']",
                "img[src*='googleusercontent']",
                "a[data-photo-index]",
                "[role='img']",
                "button[class*='photo']",
                "button[class*='image']"
            ]
            
            photo_clicked = False
            for selector in photo_selectors:
                try:
                    photo_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if photo_elements:
                        # Try clicking the first photo element
                        first_photo = photo_elements[0]
                        
                        # Scroll to element first
                        driver.execute_script("arguments[0].scrollIntoView(true);", first_photo)
                        time.sleep(1)
                        
                        # Click it
                        first_photo.click()
                        print(f"    ✓ Clicked photo thumbnail")
                        photo_clicked = True
                        break
                except Exception as e:
                    continue
            
            if not photo_clicked:
                print(f"    ✗ Could not find/click photo thumbnail")
                scraped_data["total_photos"] = 0
                return scraped_data
            
            # Wait for gallery to open
            human_delay(3, 5)
            
            # Step 2: Click on the main/large image to show all thumbnails
            print(f"    Trying to click main image to show all photos...")
            
            main_image_selectors = [
                "img[class*='photo']",
                "img[class*='image']",
                "div[class*='photo'] img",
                "img[style*='width']",
                "[role='img']"
            ]
            
            main_clicked = False
            for selector in main_image_selectors:
                try:
                    main_images = driver.find_elements(By.CSS_SELECTOR, selector)
                    if main_images:
                        # Find the largest image (main photo)
                        largest_image = None
                        max_size = 0
                        
                        for img in main_images:
                            try:
                                size = img.size
                                area = size['width'] * size['height']
                                if area > max_size:
                                    max_size = area
                                    largest_image = img
                            except:
                                continue
                        
                        if largest_image:
                            # Click the main image
                            largest_image.click()
                            print(f"    ✓ Clicked main image")
                            main_clicked = True
                            break
                except Exception as e:
                    continue
            
            if not main_clicked:
                print(f"    ✗ Could not click main image")
            
            # Wait for all thumbnails to load
            human_delay(3, 5)
            
            # Step 3: Count all thumbnail images
            print(f"    Counting all photo thumbnails...")
            
            thumbnail_selectors = [
                "img[src*='googleusercontent']",
                "button[aria-label*='photo']",
                "div[class*='thumbnail'] img",
                "div[class*='photo'] img",
                "[data-photo-index]",
                "img[class*='thumb']"
            ]
            
            max_count = 0
            for selector in thumbnail_selectors:
                try:
                    thumbnails = driver.find_elements(By.CSS_SELECTOR, selector)
                    count = len(thumbnails)
                    if count > max_count:
                        max_count = count
                        print(f"      Found {count} thumbnails with selector: {selector}")
                except:
                    continue
            
            if max_count > 0:
                scraped_data["total_photos"] = max_count
                print(f"    ✓ Total photos: {max_count}")
            else:
                print(f"    ✗ No thumbnails found")
                scraped_data["total_photos"] = 0
            
            # Close the photo viewer (press Escape or click close)
            try:
                from selenium.webdriver.common.keys import Keys
                driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
                time.sleep(1)
            except:
                pass
                
        except Exception as e:
            print(f"    Error extracting photos: {e}")
            scraped_data["total_photos"] = 0
        
        # === PRICE LEVEL ($ symbols) ===
        try:
            price_levels = re.findall(r'(?:^|\s)([\$]{1,4})(?:\s|$)', page_text)
            if price_levels:
                scraped_data["price_level_scraped"] = max(set(price_levels), key=price_levels.count)
        except:
            pass
        
        return scraped_data
        
    except Exception as e:
        print(f"  Error scraping: {e}")
        return {
            "min_price_usd": "N/A",
            "total_photos": 0,
            "price_level_scraped": ""
        }

def extract_data(place_basic, place_details, scraped_data):
    """Extract required fields"""
    geometry = place_details.get("geometry", {})
    location = geometry.get("location", {})
    
    # Price level - prefer API, fallback to scraped
    api_price_level = place_details.get("price_level", "")
    scraped_price_level = scraped_data.get("price_level_scraped", "")
    
    final_price_level = ""
    if api_price_level:
        final_price_level = "$" * api_price_level
    elif scraped_price_level:
        final_price_level = scraped_price_level
    
    # Filter primaryTypeDisplayName to only show keywords
    raw_types = place_basic.get("types", [])
    primary_type = raw_types[0] if raw_types else ""
    filtered_type = filter_primary_type(primary_type)
    
    return {
        "displayName": place_details.get("name", place_basic.get("name", "")),
        "primaryTypeDisplayName": filtered_type,
        "formattedAddress": place_details.get("formatted_address", ""),
        "latitude": location.get("lat", ""),
        "longitude": location.get("lng", ""),
        "googleMapsUri": place_details.get("url", ""),
        "businessStatus": place_details.get("business_status", ""),
        "rating": place_details.get("rating", ""),
        "userRatingCount": place_details.get("user_ratings_total", ""),
        "totalPhotoCount": scraped_data.get("total_photos", 0),
        "priceLevel": final_price_level,
        "minPrice": scraped_data.get("min_price_usd", "N/A"),
        "discountPercentage": "",
        "reservable": place_details.get("reservable", ""),
        "websiteUri": place_details.get("website", ""),
        "internationalPhoneNumber": place_details.get("international_phone_number", "")
    }

def filter_primary_type(primary_type):
    """Filter primary type to only show if it matches keywords"""
    if not primary_type:
        return ""
    
    # Check if primary type contains any of the keywords (case insensitive)
    primary_type_lower = primary_type.lower()
    
    for keyword in KEYWORDS:
        if keyword.lower() in primary_type_lower:
            return keyword
    
    # If no keyword match, return empty
    return ""

def main():
    all_places = {}
    
    print("="*80)
    print("KOH PHA NGAN HOSPITALITY DATA SCRAPER")
    print("Extracting prices (GEL→USD) and photos from Google Maps")
    print("="*80)
    
    # Search for each keyword
    for keyword in KEYWORDS:
        print(f"\nSearching nearby for: {keyword}")
        results = search_places_nearby(keyword)
        print(f"  Found {len(results)} results")
        
        for place in results:
            place_id = place.get("place_id")
            if place_id and place_id not in all_places:
                all_places[place_id] = place
        
        time.sleep(1)
    
    print(f"\n{'='*80}")
    print(f"Total unique places found: {len(all_places)}")
    print(f"{'='*80}\n")
    
    # Setup browser
    print("🤖 Setting up human-like browser...\n")
    driver = setup_driver()
    
    csv_data = []
    
    try:
        for i, (place_id, place_basic) in enumerate(all_places.items(), 1):
            place_name = place_basic.get("name", "Unknown")
            print(f"[{i}/{len(all_places)}] {place_name}")
            
            # Get API data
            place_details = get_place_details(place_id)
            human_delay(1, 2)
            
            google_maps_url = place_details.get("url", "")
            hotel_name = place_details.get("name", place_name)
            
            # Scrape Google Maps
            scraped_data = {}
            if google_maps_url:
                scraped_data = scrape_google_maps_prices_and_photos(driver, google_maps_url, hotel_name)
                
                # Longer human-like delay
                human_delay(6, 10)
            
            data = extract_data(place_basic, place_details, scraped_data)
            csv_data.append(data)
            
            # Take breaks every 3 hotels
            if i % 3 == 0:
                print(f"  😴 Taking a human-like break...")
                human_delay(15, 25)
    
    finally:
        driver.quit()
    
    # Write to CSV
    filename = "koh_pha_ngan_google_maps_data_v1.csv"
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            "displayName", "primaryTypeDisplayName", "formattedAddress",
            "latitude", "longitude", "googleMapsUri", "businessStatus", 
            "rating", "userRatingCount", "totalPhotoCount", "priceLevel", 
            "minPrice", "discountPercentage", "reservable", "websiteUri", 
            "internationalPhoneNumber"
        ])
        
        writer.writeheader()
        writer.writerows(csv_data)
    
    print(f"\n{'='*80}")
    print(f"✅ COMPLETE!")
    print(f"{'='*80}")
    print(f"Data saved to: {filename}")
    print(f"Total records: {len(csv_data)}")
    
    # Print summary
    prices_found = sum(1 for row in csv_data if row['minPrice'] and row['minPrice'] != 'N/A')
    photos_found = sum(1 for row in csv_data if row['totalPhotoCount'] > 0)
    
    print(f"\n📊 Summary:")
    print(f"   Total hotels: {len(csv_data)}")
    print(f"   Prices found (USD): {prices_found}")
    print(f"   Photo counts found: {photos_found}")
    print(f"\nNote: Prices converted from GEL to USD (rate: 1 USD = {GEL_TO_USD} GEL)")

if __name__ == "__main__":
    main()