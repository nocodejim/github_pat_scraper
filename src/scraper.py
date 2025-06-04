# src/scraper.py
import csv
import logging
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# --- Configuration ---
GITHUB_TOKENS_URL = "https://github.com/settings/tokens"
OUTPUT_FILE = "output/classic_pats_report.csv"
LOG_FILE = "logs/scraper.log"
WAIT_TIMEOUT = 20  # seconds to wait for elements to appear

# --- CSS Selectors (These might change if GitHub updates its UI) ---
# It's crucial to verify these selectors if the script fails to find elements.
# This targets the frame/container for classic PATs
TOKEN_PAGE_IDENTIFIER_ELEMENT_XPATH = "//h2[contains(text(), 'Personal access tokens (classic)')]"
# This selector targets each row representing a classic token.
# It looks for Box-rows within the specific turbo-frame for classic PATs.
# If this is too fragile, a broader selector might be needed, with more checks in the code.
TOKEN_ROWS_SELECTOR = 'turbo-frame#js-settings-tokens-classic-PATs-table div.Box-row'
# Within each row:
TOKEN_NAME_SELECTOR = 'a > strong'  # The token name (note) is usually a strong tag within an anchor
TOKEN_EXPIRATION_SELECTOR_RELATIVE_TIME = 'relative-time' # for <relative-time datetime="...">
TOKEN_EXPIRATION_FALLBACK_TEXT_SELECTOR = 'div > span' # If relative-time is not found, look for text like "No expiration."

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler() # Also print to console
    ]
)

def setup_driver():
    """Initializes and returns a Selenium Chrome WebDriver."""
    logging.info("Setting up Chrome WebDriver...")
    try:
        # Automatically download and manage chromedriver
        service = Service(ChromeDriverManager().install())
        
        # Chrome options
        chrome_options = webdriver.ChromeOptions()
        # chrome_options.add_argument("--headless")  # Run headless (no UI) - REMOVE FOR LOGIN
        # For GitHub login, it's better to run with UI first so user can intervene if needed.
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1280x800")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")

        driver = webdriver.Chrome(service=service, options=chrome_options)
        logging.info("✅ Chrome WebDriver setup complete.")
        return driver
    except Exception as e:
        logging.error(f"❌ Failed to setup Chrome WebDriver: {e}")
        logging.error("Ensure Google Chrome is installed. If issues persist with chromedriver download, you might need to install it manually and adjust the script or your system PATH.")
        raise

def check_login_and_navigate(driver):
    """Navigates to the tokens page and checks if the user is logged in."""
    logging.info(f"Navigating to {GITHUB_TOKENS_URL}...")
    driver.get(GITHUB_TOKENS_URL)
    time.sleep(3) # Allow some time for potential redirects or JS loading

    # Check if we were redirected to a login page
    if "login" in driver.current_url.lower() or "auth" in driver.current_url.lower():
        logging.warning("⚠️ It seems you are not logged into GitHub in this browser session.")
        logging.info("Please log in to GitHub in the opened browser window.")
        logging.info("Once logged in and on the 'Personal access tokens (classic)' page, the script will attempt to continue.")
        # Wait for user to manually log in and for the correct page to load
        try:
            WebDriverWait(driver, 300).until( # Wait up to 5 minutes for user login
                EC.presence_of_element_located((By.XPATH, TOKEN_PAGE_IDENTIFIER_ELEMENT_XPATH))
            )
            logging.info("✅ Successfully navigated to the tokens page after login.")
            # Re-fetch the target URL to ensure we are on the final page.
            driver.get(GITHUB_TOKENS_URL)
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.XPATH, TOKEN_PAGE_IDENTIFIER_ELEMENT_XPATH))
            )
        except TimeoutException:
            logging.error("❌ Timed out waiting for login or navigation to the tokens page.")
            logging.error("Please ensure you are logged in and can manually access the classic tokens page.")
            return False
    
    # Verify we are on the classic tokens page by looking for a specific header
    try:
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.XPATH, TOKEN_PAGE_IDENTIFIER_ELEMENT_XPATH))
        )
        logging.info("✅ Successfully on the 'Personal access tokens (classic)' page.")
        return True
    except TimeoutException:
        logging.error(f"❌ Failed to find the classic tokens page identifier: '{TOKEN_PAGE_IDENTIFIER_ELEMENT_XPATH}'.")
        logging.error("Ensure you are logged in and the URL is correct. The page structure might have changed.")
        return False

def scrape_tokens(driver):
    """Scrapes classic PATs from the current page."""
    logging.info("🔍 Starting token scraping process...")
    tokens_data = []

    try:
        # Wait for the token rows to be present
        token_rows = WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, TOKEN_ROWS_SELECTOR))
        )
        
        if not token_rows:
            logging.info("ℹ️ No classic personal access tokens found on the page.")
            return []

        logging.info(f"Found {len(token_rows)} potential token entries.")

        for row in token_rows:
            token_name = "N/A"
            expiration_date_str = "N/A"

            # Get token name
            try:
                name_element = row.find_element(By.CSS_SELECTOR, TOKEN_NAME_SELECTOR)
                token_name = name_element.text.strip() if name_element.text.strip() else "Unnamed Token"
            except NoSuchElementException:
                logging.warning("Could not find token name element for a row. Using 'N/A'. Row HTML: " + row.get_attribute('outerHTML')[:100])


            # Get expiration date
            # GitHub uses <relative-time> for dates, which is good.
            # Fallback if structure changes or for "No expiration".
            try:
                # First, try to find the <relative-time> element which has a 'datetime' attribute
                expiry_element_relative_time = row.find_element(By.TAG_NAME, TOKEN_EXPIRATION_SELECTOR_RELATIVE_TIME)
                expiry_datetime_attr = expiry_element_relative_time.get_attribute('datetime')
                # Convert ISO 8601 datetime to a more readable format, e.g., "YYYY-MM-DD"
                dt_object = datetime.fromisoformat(expiry_datetime_attr.replace('Z', '+00:00'))
                expiration_date_str = dt_object.strftime('%Y-%m-%d')
            except NoSuchElementException:
                # If <relative-time> not found, try to find text like "No expiration" or "Expires on..."
                # This part might need refinement based on actual HTML for "No expiration"
                try:
                    # Look for a span or div that might contain "No expiration" or "Expires..."
                    # This is less precise and might need adjustment based on GitHub's specific HTML.
                    # Typically, the expiration info is in the second 'flex-auto text-right' div
                    expiry_text_elements = row.find_elements(By.CSS_SELECTOR, ".flex-auto.text-right .text-small.text-gray span")
                    found_expiry_text = False
                    for el in expiry_text_elements:
                        text_content = el.text.strip()
                        if "No expiration" in text_content:
                            expiration_date_str = "No expiration"
                            found_expiry_text = True
                            break
                        elif "Expires on" in text_content: # Fallback if relative-time missing but text exists
                            expiration_date_str = text_content 
                            found_expiry_text = True
                            break
                    if not found_expiry_text:
                         expiration_date_str = "Expiration not found" # Default if nothing specific is identified
                except NoSuchElementException:
                    logging.warning(f"Could not find expiration date element for token '{token_name}'. Row HTML: " + row.get_attribute('outerHTML')[:100])
                    expiration_date_str = "N/A (parsing error)"
            except Exception as e:
                logging.error(f"Error parsing expiration for token '{token_name}': {e}")
                expiration_date_str = "Error parsing expiry"

            if token_name != "N/A": # Only add if we got a name
                tokens_data.append({"Token Name": token_name, "Expiration Date": expiration_date_str})
                logging.info(f"  ✔️ Scraped: Name='{token_name}', Expiry='{expiration_date_str}'")
            else:
                logging.warning(f"  ⚠️ Skipped a row due to missing token name.")


    except TimeoutException:
        logging.warning(f"⏰ Timed out waiting for token rows using selector: '{TOKEN_ROWS_SELECTOR}'. No tokens scraped or page structure changed.")
    except Exception as e:
        logging.error(f"❌ An error occurred during scraping: {e}")

    return tokens_data

def save_to_csv(data, filename):
    """Saves the scraped data to a CSV file."""
    if not data:
        logging.info("No data to save to CSV.")
        # Create empty CSV with headers if file doesn't exist or is empty
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ["Token Name", "Expiration Date"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
        logging.info(f"Wrote headers to empty CSV: {filename}")
        return

    logging.info(f"💾 Saving data to {filename}...")
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ["Token Name", "Expiration Date"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
        logging.info(f"✅ Data successfully saved to {filename}.")
    except IOError as e:
        logging.error(f"❌ IOError saving data to CSV: {e}")
    except Exception as e:
        logging.error(f"❌ An unexpected error occurred while saving to CSV: {e}")


def main():
    """Main function to orchestrate the scraping process."""
    logging.info("--- GitHub Classic PAT Scraper Initializing ---")
    driver = None
    try:
        driver = setup_driver()
        if not check_login_and_navigate(driver):
            logging.error("Could not verify login or navigate to the correct page. Exiting.")
            return

        # Optional: Give user a few seconds to see the page or if any manual interaction is needed
        # logging.info("Pausing for 5 seconds before scraping starts...")
        # time.sleep(5)

        scraped_tokens = scrape_tokens(driver)

        if scraped_tokens:
            save_to_csv(scraped_tokens, OUTPUT_FILE)
        else:
            logging.info("No tokens were scraped. An empty CSV with headers will be created if it doesn't exist.")
            save_to_csv([], OUTPUT_FILE) # Ensure CSV is created with headers

    except Exception as e:
        logging.error(f"🚨 An critical error occurred in the main process: {e}")
    finally:
        if driver:
            logging.info("Closing WebDriver...")
            driver.quit()
        logging.info("--- GitHub Classic PAT Scraper Finished ---")

if __name__ == "__main__":
    # Create output and logs directory if they don't exist (Python 3.2+)
    import os
    os.makedirs("output", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    main()