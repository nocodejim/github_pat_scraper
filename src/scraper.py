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
TOKEN_PAGE_IDENTIFIER_ELEMENT_XPATH = "//h2[contains(text(), 'Personal access tokens (classic)')]"
TOKEN_ROWS_SELECTOR = 'turbo-frame#js-settings-tokens-classic-PATs-table div.Box-row'
TOKEN_NAME_SELECTOR = 'a > strong'
TOKEN_EXPIRATION_SELECTOR_RELATIVE_TIME = 'relative-time'
# For fallback, we'll inspect the text content of a broader container
EXPIRY_TEXT_CONTAINER_SELECTOR_FALLBACK = "div.flex-auto.text-right .text-small.text-gray"


# --- Logging Setup ---
# For debugging, you might want to change level to logging.DEBUG,
# but for this iteration, INFO level logs are enhanced.
logging.basicConfig(
    level=logging.INFO, # Keep as INFO, but added more info-level logs for debugging
    format="%(asctime)s [%(levelname)s] - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w'), # Overwrite log file each run for clarity
        logging.StreamHandler()
    ]
)

def setup_driver():
    """Initializes and returns a Selenium Chrome WebDriver."""
    logging.info("Setting up Chrome WebDriver...")
    try:
        service = Service(ChromeDriverManager().install())
        chrome_options = webdriver.ChromeOptions()
        # Important: To allow GitHub login, do NOT run headless initially.
        # chrome_options.add_argument("--headless") 
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
    time.sleep(3) # Allow some time for potential redirects or JS loading

    # Check if we were redirected to a login page
    # Looking for "login" or "auth" in URL, or title containing "Sign in"
    current_url_lower = driver.current_url.lower()
    page_title_lower = driver.title.lower()

    if "login" in current_url_lower or "auth" in current_url_lower or "sign in" in page_title_lower:
        logging.warning("⚠️ It seems you are not logged into GitHub in this browser session.")
        logging.info("Please log in to GitHub in the opened browser window.")
        logging.info("Once logged in and on the 'Personal access tokens (classic)' page, the script will attempt to continue.")
        # Wait for user to manually log in and for the correct page to load
        try:
            WebDriverWait(driver, 300).until( # Wait up to 5 minutes for user login
                EC.presence_of_element_located((By.XPATH, TOKEN_PAGE_IDENTIFIER_ELEMENT_XPATH))
            )
            logging.info("✅ Successfully detected navigation to the tokens page after potential login.")
            # It's good practice to re-fetch the target URL to ensure we are on the final page state.
            driver.get(GITHUB_TOKENS_URL)
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.XPATH, TOKEN_PAGE_IDENTIFIER_ELEMENT_XPATH))
            )
        except TimeoutException:
            logging.error("❌ Timed out waiting for login or navigation to the tokens page.", exc_info=True)
            logging.error("Please ensure you are logged in and can manually access the classic tokens page: " + GITHUB_TOKENS_URL)
            return False
    
    # Verify we are on the classic tokens page by looking for a specific header
    try:
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.XPATH, TOKEN_PAGE_IDENTIFIER_ELEMENT_XPATH))
        )
        logging.info("✅ Successfully on the 'Personal access tokens (classic)' page.")
        return True
    except TimeoutException:
        logging.error(f"❌ Failed to find the classic tokens page identifier: '{TOKEN_PAGE_IDENTIFIER_ELEMENT_XPATH}'.", exc_info=True)
        logging.error("Ensure you are logged in and the URL is correct. The page structure might have changed.")
        return False

def scrape_tokens(driver):
    """Scrapes classic PATs from the current page."""
    logging.info("🔍 Starting token scraping process...")
    tokens_data = []

    try:
        logging.info(f"Attempting to find token rows with CSS selector: '{TOKEN_ROWS_SELECTOR}'")
        # It's better to wait for visibility or presence of at least one, then get all.
        # This ensures the container itself is loaded.
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, TOKEN_ROWS_SELECTOR.split(' ')[0])) # Wait for the turbo-frame
        )
        token_rows = driver.find_elements(By.CSS_SELECTOR, TOKEN_ROWS_SELECTOR) # Get all matching rows
        
        if not token_rows:
            logging.info(f"ℹ️ No token rows found using selector '{TOKEN_ROWS_SELECTOR}'. This might mean no classic tokens exist, or the selector is no longer valid for the current page structure.")
            # To help debug, let's log a snippet of the page if no rows are found
            try:
                page_body_snippet = driver.find_element(By.TAG_NAME, "body").get_attribute('outerHTML')[:1000]
                logging.info(f"Page body snippet (if no rows found): {page_body_snippet}...")
            except Exception as e_body_log:
                logging.warning(f"Could not log page body snippet: {e_body_log}")
            return []

        logging.info(f"Found {len(token_rows)} potential token entries/rows based on selector '{TOKEN_ROWS_SELECTOR}'.")

        for i, row_element in enumerate(token_rows):
            logging.info(f"--- Processing potential token row {i+1}/{len(token_rows)} ---")
            try:
                # Log the HTML of the row for manual inspection
                row_html_snippet = row_element.get_attribute('outerHTML')[:700] # Get a snippet
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
                # Log child elements if name not found, to help debug selector path
                try:
                    child_elements_details = []
                    # Get direct children first, then maybe some key descendants
                    direct_children = row_element.find_elements(By.XPATH, "./*") 
                    for child_idx, child in enumerate(direct_children[:5]): # Log details of first 5 direct children
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
                    # This case should be rare if <relative-time> is present but lacks datetime
                    expiration_date_str = expiry_relative_time_element.text.strip() if expiry_relative_time_element.text else "Relative-time text (no datetime)"
                    logging.warning(f"Row {i+1}: <relative-time> tag found but 'datetime' attribute missing or empty. Text: '{expiration_date_str}'")

            except NoSuchElementException:
                logging.info(f"Row {i+1}: <relative-time> tag NOT found for expiration. Trying fallback text selector '{EXPIRY_TEXT_CONTAINER_SELECTOR_FALLBACK}'.")
                try:
                    # Look for the specific container that usually holds "Expires on..." or "No expiration"
                    expiry_text_container = row_element.find_element(By.CSS_SELECTOR, EXPIRY_TEXT_CONTAINER_SELECTOR_FALLBACK)
                    expiry_text_content = expiry_text_container.text.strip()
                    logging.info(f"Row {i+1}: Expiry fallback text container content: '{expiry_text_content}'")

                    if "No expiration" in expiry_text_content:
                        expiration_date_str = "No expiration"
                        logging.info(f"Row {i+1}: Using fallback: 'No expiration' text found.")
                    elif "Expires on" in expiry_text_content: # Example: "Expires on Jan 1, 2025."
                        expiration_date_str = expiry_text_content 
                        logging.info(f"Row {i+1}: Using fallback: Expiration text found: '{expiration_date_str}'.")
                    # Add more specific checks if GitHub uses other phrases
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

            # Add to list if a name was reasonably found (not the default "N/A (Not Found)")
            if token_name != "N/A (Not Found)" and token_name != "Unnamed Token (parsed empty)":
                tokens_data.append({"Token Name": token_name, "Expiration Date": expiration_date_str})
                logging.info(f"Row {i+1}: ✔️ Successfully parsed and added to list: Name='{token_name}', Expiry='{expiration_date_str}'")
            else:
                logging.warning(f"Row {i+1}: ⚠️ Skipped adding to list. Token Name was '{token_name}'. This row might not be a valid token or name parsing failed critically.")
            logging.info(f"--- Finished processing row {i+1} ---")

    except TimeoutException:
        logging.warning(f"⏰ Timed out waiting for token rows using selector: '{TOKEN_ROWS_SELECTOR}'. No tokens scraped or page structure changed.", exc_info=True)
    except Exception as e:
        logging.error(f"❌ An unexpected error occurred during the scraping process: {e}", exc_info=True)

    if not tokens_data:
        logging.warning("No token data was successfully extracted into the list. The output CSV will be empty (except for headers). Review logs for parsing issues.")
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
            if data: # Only write rows if data is not empty
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
    # Create output and logs directory if they don't exist (Python 3.2+)
    import os
    os.makedirs("output", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    main()
