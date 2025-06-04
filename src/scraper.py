# src/scraper.py
import csv
import logging
import time
import os # Added for saving page source optionally
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
PAGE_SOURCE_LOG_FILE = "output/page_source_at_timeout.html" # For dumping page source on error
WAIT_TIMEOUT = 20  # seconds to wait for elements to appear

# --- CSS Selectors (These might change if GitHub updates its UI) ---
TOKEN_PAGE_IDENTIFIER_ELEMENT_XPATH = "//h2[contains(text(), 'Personal access tokens (classic)')]"
# NEW SELECTOR: Targets Box-row divs whose ID starts with "user_token_classic_"
# This is based on common GitHub patterns for such elements.
TOKEN_ROWS_SELECTOR = 'div.Box-row[id^="user_token_classic_"]'
TOKEN_NAME_SELECTOR = 'a > strong' # Often the token name (note) is a strong tag within an anchor
TOKEN_EXPIRATION_SELECTOR_RELATIVE_TIME = 'relative-time' # for <relative-time datetime="...">
EXPIRY_TEXT_CONTAINER_SELECTOR_FALLBACK = "div.flex-auto.text-right .text-small.text-gray"


# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w'), # Overwrite log file each run
        logging.StreamHandler()
    ]
)

def setup_driver():
    """Initializes and returns a Selenium Chrome WebDriver."""
    logging.info("Setting up Chrome WebDriver...")
    try:
        service = Service(ChromeDriverManager().install())
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1280x800")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        logging.info("✅ Chrome WebDriver setup complete.")
        return driver
    except Exception as e:
        logging.error(f"❌ Failed to setup Chrome WebDriver: {e}", exc_info=True)
        logging.error("Ensure Google Chrome is installed. If issues persist with chromedriver download, you might need to install it manually and adjust the script or your system PATH.")
        raise

def check_login_and_navigate(driver):
    """Navigates to the tokens page and checks if the user is logged in."""
    logging.info(f"Navigating to {GITHUB_TOKENS_URL}...")
    driver.get(GITHUB_TOKENS_URL)
    time.sleep(3) 

    current_url_lower = driver.current_url.lower()
    page_title_lower = driver.title.lower()

    if "login" in current_url_lower or "auth" in current_url_lower or "sign in" in page_title_lower:
        logging.warning("⚠️ It seems you are not logged into GitHub in this browser session.")
        logging.info("Please log in to GitHub in the opened browser window.")
        logging.info("Once logged in and on the 'Personal access tokens (classic)' page, the script will attempt to continue.")
        try:
            WebDriverWait(driver, 300).until( 
                EC.presence_of_element_located((By.XPATH, TOKEN_PAGE_IDENTIFIER_ELEMENT_XPATH))
            )
            logging.info("✅ Successfully detected navigation to the tokens page after potential login.")
            driver.get(GITHUB_TOKENS_URL) 
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.XPATH, TOKEN_PAGE_IDENTIFIER_ELEMENT_XPATH))
            )
        except TimeoutException:
            logging.error("❌ Timed out waiting for login or navigation to the tokens page.", exc_info=True)
            logging.error("Please ensure you are logged in and can manually access the classic tokens page: " + GITHUB_TOKENS_URL)
            return False
    
    try:
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.XPATH, TOKEN_PAGE_IDENTIFIER_ELEMENT_XPATH))
        )
        logging.info("✅ Successfully on the 'Personal access tokens (classic)' page.")
        return True
    except TimeoutException:
        logging.error(f"❌ Failed to find the classic tokens page identifier: '{TOKEN_PAGE_IDENTIFIER_ELEMENT_XPATH}'.", exc_info=True)
        return False

def scrape_tokens(driver):
    """Scrapes classic PATs from the current page."""
    logging.info("🔍 Starting token scraping process...")
    tokens_data = []

    try:
        logging.info(f"Attempting to find token rows with NEW CSS selector: '{TOKEN_ROWS_SELECTOR}'")
        # Wait for at least one element matching the selector, or timeout.
        token_rows = WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, TOKEN_ROWS_SELECTOR))
        )
        # If the above does not time out, token_rows will be a list of found elements.
        # If it times out (because no elements found), the except TimeoutException block below will handle it.

    except TimeoutException:
        logging.warning(f"⏰ Timed out waiting for token rows using selector: '{TOKEN_ROWS_SELECTOR}'. This means no elements matched this selector within {WAIT_TIMEOUT} seconds.")
        logging.info("This could be because there are no classic tokens, or the page structure has changed significantly.")
        try:
            page_source = driver.page_source
            logging.info(f"Page source at time of timeout (first 3000 chars):\n{page_source[:3000]}")
            # Save the full page source to a file for detailed inspection
            with open(PAGE_SOURCE_LOG_FILE, "w", encoding="utf-8") as f:
               f.write(page_source)
            logging.info(f"Full page source saved to {PAGE_SOURCE_LOG_FILE} for debugging.")
        except Exception as e_ps:
            logging.error(f"Could not get/save page source after timeout: {e_ps}")
        return [] # Return empty list as no tokens found/matched

    # If we are here, token_rows contains one or more elements
    if not token_rows: # Should not happen if WebDriverWait worked as expected, but as a safeguard.
        logging.info(f"ℹ️ No token rows found (list is empty) even after WebDriverWait did not time out using selector '{TOKEN_ROWS_SELECTOR}'. This is unexpected.")
        return []

    logging.info(f"Found {len(token_rows)} potential token entries/rows based on selector '{TOKEN_ROWS_SELECTOR}'.")

    for i, row_element in enumerate(token_rows):
        logging.info(f"--- Processing potential token row {i+1}/{len(token_rows)} ---")
        try:
            row_html_snippet = row_element.get_attribute('outerHTML')[:700] 
            logging.info(f"Row {i+1} HTML snippet: {row_html_snippet} ...")
        except Exception as e_html:
            logging.warning(f"Could not get HTML for row {i+1}: {e_html}")

        token_name = "N/A (Not Found)"
        expiration_date_str = "N/A (Not Found)"

        # Get token name
        try:
            name_element = row_element.find_element(By.CSS_SELECTOR, TOKEN_NAME_SELECTOR)
            token_name_text = name_element.text.strip()
            token_name = token_name_text if token_name_text else "Unnamed Token (parsed empty)"
            logging.info(f"Row {i+1}: Found token name '{token_name}' using selector '{TOKEN_NAME_SELECTOR}'")
        except NoSuchElementException:
            logging.warning(f"Row {i+1}: Token name element NOT found using selector '{TOKEN_NAME_SELECTOR}'.")
            try:
                child_elements_details = []
                direct_children = row_element.find_elements(By.XPATH, "./*") 
                for child_idx, child in enumerate(direct_children[:5]):
                     child_elements_details.append(f"Direct Child {child_idx}: tag={child.tag_name}, text='{child.text[:30].strip() if child.text else ''}'")
                logging.info(f"Row {i+1} Direct Child details for name search (first 5): {'; '.join(child_elements_details)}")
            except Exception as e_child_debug:
                logging.info(f"Row {i+1} Could not get detailed child elements for debugging: {e_child_debug}")

        # Get expiration date
        try:
            expiry_relative_time_element = row_element.find_element(By.TAG_NAME, TOKEN_EXPIRATION_SELECTOR_RELATIVE_TIME)
            expiry_datetime_attr = expiry_relative_time_element.get_attribute('datetime')
            if expiry_datetime_attr:
                dt_object = datetime.fromisoformat(expiry_datetime_attr.replace('Z', '+00:00'))
                expiration_date_str = dt_object.strftime('%Y-%m-%d')
                logging.info(f"Row {i+1}: Found expiration '{expiration_date_str}' using <relative-time> tag with datetime='{expiry_datetime_attr}'.")
            else:
                expiration_date_str = expiry_relative_time_element.text.strip() if expiry_relative_time_element.text else "Relative-time text (no datetime)"
                logging.warning(f"Row {i+1}: <relative-time> tag found but 'datetime' attribute missing or empty. Text: '{expiration_date_str}'")

        except NoSuchElementException:
            logging.info(f"Row {i+1}: <relative-time> tag NOT found for expiration. Trying fallback text selector '{EXPIRY_TEXT_CONTAINER_SELECTOR_FALLBACK}'.")
            try:
                expiry_text_container = row_element.find_element(By.CSS_SELECTOR, EXPIRY_TEXT_CONTAINER_SELECTOR_FALLBACK)
                expiry_text_content = expiry_text_container.text.strip()
                logging.info(f"Row {i+1}: Expiry fallback text container content: '{expiry_text_content}'")

                if "No expiration" in expiry_text_content:
                    expiration_date_str = "No expiration"
                    logging.info(f"Row {i+1}: Using fallback: 'No expiration' text found.")
                elif "Expires on" in expiry_text_content: 
                    expiration_date_str = expiry_text_content 
                    logging.info(f"Row {i+1}: Using fallback: Expiration text found: '{expiration_date_str}'.")
                else:
                    expiration_date_str = f"Expiry text not recognized ('{expiry_text_content}')"
                    logging.warning(f"Row {i+1}: Expiry fallback text found but not recognized: '{expiry_text_content}'")
            except NoSuchElementException:
                logging.warning(f"Row {i+1}: Expiration fallback text container NOT found using selector '{EXPIRY_TEXT_CONTAINER_SELECTOR_FALLBACK}'.")
            except Exception as e_fallback:
                logging.error(f"Row {i+1}: Error parsing expiration with fallback for token '{token_name}': {e_fallback}", exc_info=True)
                expiration_date_str = "Error in fallback (see logs)"
        except Exception as e_expiry:
            logging.error(f"Row {i+1}: General error parsing expiration for token '{token_name}': {e_expiry}", exc_info=True)
            expiration_date_str = "Error parsing (see logs)"

        if token_name != "N/A (Not Found)" and token_name != "Unnamed Token (parsed empty)":
            tokens_data.append({"Token Name": token_name, "Expiration Date": expiration_date_str})
            logging.info(f"Row {i+1}: ✔️ Successfully parsed and added to list: Name='{token_name}', Expiry='{expiration_date_str}'")
        else:
            logging.warning(f"Row {i+1}: ⚠️ Skipped adding to list. Token Name was '{token_name}'. This row might not be a valid token or name parsing failed critically.")
        logging.info(f"--- Finished processing row {i+1} ---")

    if not tokens_data and len(token_rows or []) > 0 : # If rows were found but nothing was added
        logging.warning("Potential token rows were found, but no data was successfully extracted into the list. Check parsing logic and HTML snippets in logs.")
    elif not tokens_data: # This case is now mainly handled by the TimeoutException or if token_rows list becomes empty unexpectedly
        logging.warning("No token data was successfully extracted into the list. The output CSV will be empty (except for headers).")
    return tokens_data

def save_to_csv(data, filename):
    """Saves the scraped data to a CSV file."""
    if not data:
        logging.info("No data to save to CSV. Writing headers only.")
    else:
        logging.info(f"💾 Saving {len(data)} token(s) to {filename}...")
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ["Token Name", "Expiration Date"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            if data: 
                writer.writerows(data)
        logging.info(f"✅ Data (or headers) successfully saved to {filename}.")
    except IOError as e:
        logging.error(f"❌ IOError saving data to CSV: {e}", exc_info=True)
    except Exception as e:
        logging.error(f"❌ An unexpected error occurred while saving to CSV: {e}", exc_info=True)

def main():
    """Main function to orchestrate the scraping process."""
    logging.info("--- GitHub Classic PAT Scraper Initializing ---")
    driver = None
    try:
        driver = setup_driver()
        if not check_login_and_navigate(driver):
            logging.error("Could not verify login or navigate to the correct page. Exiting.")
            return

        scraped_tokens = scrape_tokens(driver)
        save_to_csv(scraped_tokens, OUTPUT_FILE)

    except Exception as e:
        logging.error(f"🚨 An critical error occurred in the main process: {e}", exc_info=True)
    finally:
        if driver:
            logging.info("Closing WebDriver...")
            driver.quit()
        logging.info("--- GitHub Classic PAT Scraper Finished ---")

if __name__ == "__main__":
    os.makedirs("output", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    main()
