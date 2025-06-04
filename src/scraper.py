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
GITHUB_TOKENS_URL = "https://github.com/orgs/Cincinnati-Insurance/people"
OUTPUT_FILE = "output/org_sso_tokens_report.csv"
LOG_FILE = "logs/scraper.log"
PAGE_SOURCE_LOG_FILE = "output/page_source_at_timeout.html" # For dumping page source on error
SSO_PAGE_SOURCE_DEBUG_PATH = "output/debug_sso_page_source_{username}.html" # For SSO page specific debug
WAIT_TIMEOUT = 20  # seconds to wait for elements to appear

# --- CSS Selectors (These might change if GitHub updates its UI) ---
TOKEN_PAGE_IDENTIFIER_ELEMENT_XPATH = "//h2[contains(text(), 'Personal access tokens (classic)')]"

# --- CSS Selectors for Organization Pages ---
ORG_PEOPLE_PAGE_IDENTIFIER_XPATH = "//h1[contains(text(), 'People')]" # Example, verify later
USER_PROFILE_LINK_SELECTOR = "a[data-hovercard-type='user']" # Example, verify later
PAGINATION_NEXT_BUTTON_SELECTOR = ".paginate-container button.next_page" # Example, verify later

# --- CSS Selectors for SSO Page ---
SSO_PAGE_IDENTIFIER_SPAN_TEXT = "SSO identity linked" # From issue description
SSO_AUTHORIZED_CREDENTIALS_SECTION_HEADING_XPATH = "//h2[contains(text(), 'Authorized credentials')]" # Example
SSO_TOKEN_ROW_SELECTOR = "div.Box-row.d-flex.flex-column.token-type" # From issue description
SSO_TOKEN_NAME_SELECTOR = "span.token-description" # Placeholder, needs inspection
SSO_TOKEN_EXPIRATION_SELECTOR = "span.color-fg-muted" # Placeholder, needs inspection
#
# --- IMPORTANT: Debugging CSS Selectors (June 2024 Update) ---
# The CSS selectors below were updated based on analysis of a new GitHub tokens page HTML structure
# provided by the user (June 2024). GitHub's UI can change, so these selectors might break.
#
# Current Key Selectors:
#   - TOKEN_ROWS_SELECTOR = 'div.access-token[id^="access-token-"]' (for each token's main container)
#   - TOKEN_NAME_SELECTOR = 'span.token-description > strong > a' (for the token's name/note)
#   - NEW_TOKEN_EXPIRATION_TEXT_SELECTOR = 'div span.color-fg-attention > a.color-fg-attention' (for expiration text like "Expired on ...")
#   - Fallback for expiration: The code also checks for a <relative-time> tag if the above selector fails.
#
# If `scrape_tokens` times out waiting for `TOKEN_ROWS_SELECTOR` (no token rows found):
# 1. This means `TOKEN_ROWS_SELECTOR` is likely outdated.
# 2. The script *should* save the page HTML to `output/page_source_at_timeout.html`.
#    Inspect this file to understand the current HTML structure for token rows.
# 3. Use browser developer tools (Ctrl+Shift+I or Cmd+Option+I) on the live GitHub tokens page:
#    a. Inspect an individual token row element.
#    b. Right-click the element and choose "Copy > Copy selector" or manually craft a new, unique CSS selector
#       for `TOKEN_ROWS_SELECTOR`.
#    c. Test your new selector in the browser's console: `document.querySelectorAll('YOUR_SELECTOR_HERE')`.
#       It should return a list of all token row elements.
#
# If token rows ARE found, but parsing fails for name or expiration (e.g., "N/A (Not Found)"):
# 1. Examine the "Row X HTML snippet" logged for each processed row. This shows the HTML the script sees.
# 2. This snippet will help you verify if `TOKEN_NAME_SELECTOR` or `NEW_TOKEN_EXPIRATION_TEXT_SELECTOR`
#    (and the <relative-time> fallback) are still valid within the row's structure.
# 3. Adjust these selectors based on the logged HTML snippet or by inspecting `page_source_at_timeout.html`
#    (if saved) or the live page with developer tools.
#
# Remember to update the constant values in this script with any new working selectors.
# ---
TOKEN_ROWS_SELECTOR = 'div.access-token[id^="access-token-"]' # Updated June 2024
TOKEN_NAME_SELECTOR = 'span.token-description > strong > a' # Updated June 2024
# For tokens that show "Expired on..." or similar text. Updated June 2024.
NEW_TOKEN_EXPIRATION_TEXT_SELECTOR = 'div span.color-fg-attention > a.color-fg-attention'
# Old selectors TOKEN_EXPIRATION_SELECTOR_RELATIVE_TIME and EXPIRY_TEXT_CONTAINER_SELECTOR_FALLBACK were removed
# as the expiration parsing logic has been updated (June 2024) to use NEW_TOKEN_EXPIRATION_TEXT_SELECTOR
# and a <relative-time> tag fallback.
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
        logging.info("Once logged in and on the 'Organization People' page, the script will attempt to continue.")
        try:
            WebDriverWait(driver, 300).until( 
                EC.presence_of_element_located((By.XPATH, ORG_PEOPLE_PAGE_IDENTIFIER_XPATH))
            )
            logging.info("✅ Successfully detected navigation to the Organization People page after potential login.")
            # It's good practice to re-assert the target URL after a manual login flow.
            # driver.get(GITHUB_TOKENS_URL) # Already on this URL or navigated by user
            # Re-wait for the identifier on the current page.
            WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.XPATH, ORG_PEOPLE_PAGE_IDENTIFIER_XPATH))
            )
        except TimeoutException:
            logging.error("❌ Timed out waiting for login or navigation to the Organization People page.", exc_info=True)
            logging.error("Please ensure you are logged in and can manually access the Organization People page: " + GITHUB_TOKENS_URL)
            return False
    
    try:
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.XPATH, ORG_PEOPLE_PAGE_IDENTIFIER_XPATH))
        )
        logging.info("✅ Successfully on the 'Organization People' page.")
        return True
    except TimeoutException:
        logging.error(f"❌ Failed to find the Organization People page identifier: '{ORG_PEOPLE_PAGE_IDENTIFIER_XPATH}'.", exc_info=True)
        return False

def get_all_user_sso_links(driver, org_name="Cincinnati-Insurance"):
    """
    Collects URLs for the SSO page of each user in an organization.
    Navigates through paginated lists of organization members.
    """
    sso_page_urls = []
    processed_usernames = set()
    logging.info(f"Starting to collect user SSO links for organization: {org_name}")

    while True:
        try:
            user_elements = WebDriverWait(driver, WAIT_TIMEOUT).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, USER_PROFILE_LINK_SELECTOR))
            )
            logging.info(f"Found {len(user_elements)} user profile links on the current page.")
        except TimeoutException:
            logging.warning("No user profile links found on the current page or timed out waiting.")
            break

        if not user_elements: # Should be caught by TimeoutException, but as a safeguard
            logging.info("User elements list is empty. Breaking pagination.")
            break

        new_users_found_on_page = 0
        current_page_user_elements = user_elements # Keep a reference to current page's elements for staleness check

        for user_element in user_elements:
            try:
                href = user_element.get_attribute('href')
                if href:
                    username = href.split('/')[-1]
                    if username and username not in processed_usernames:
                        sso_url = f"https://github.com/orgs/{org_name}/{username}/sso"
                        sso_page_urls.append(sso_url)
                        processed_usernames.add(username)
                        new_users_found_on_page += 1
                        logging.info(f"Collected SSO URL: {sso_url}")
            except Exception as e:
                logging.warning(f"Could not extract username or construct SSO URL from element: {user_element.get_attribute('outerHTML') if hasattr(user_element, 'get_attribute') else 'N/A'}. Error: {e}")

        if new_users_found_on_page == 0 and user_elements:
            logging.info("All users on this page were already processed or no valid new usernames found.")

        # Handle Pagination
        try:
            next_button = driver.find_element(By.CSS_SELECTOR, PAGINATION_NEXT_BUTTON_SELECTOR)
            if next_button.is_enabled():
                logging.info("Clicking 'Next' page button for organization users.")
                driver.execute_script("arguments[0].click();", next_button)
                time.sleep(3) # Basic wait for page load initiated by JS click

                # Wait for the old user elements to become stale, indicating new content has loaded
                WebDriverWait(driver, WAIT_TIMEOUT).until(
                    EC.staleness_of(current_page_user_elements[0])
                )
                logging.info("Page refreshed, proceeding to scrape next page.")
            else:
                logging.info("Next page button is disabled. End of user pagination.")
                break
        except NoSuchElementException:
            logging.info("No 'Next' page button found. End of user pagination.")
            break
        except TimeoutException:
            logging.warning("Timed out waiting for page to refresh after clicking next (staleness check). Assuming end of pagination or very slow load.")
            break
        except Exception as e:
            logging.error(f"Error during pagination: {e}", exc_info=True)
            break

    logging.info(f"Collected a total of {len(sso_page_urls)} unique user SSO URLs.")
    return sso_page_urls

def scrape_sso_tokens_for_user(driver, user_sso_url, username):
    """Scrapes SSO token information for a specific user from their SSO page."""
    logging.info(f"Navigating to SSO page for user {username}: {user_sso_url}")
    driver.get(user_sso_url)
    user_tokens_data = []

    try:
        WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.XPATH, f"//span[contains(text(), '{SSO_PAGE_IDENTIFIER_SPAN_TEXT}')]"))
        )
        logging.info(f"Successfully on SSO page for user {username}.")
    except TimeoutException:
        logging.warning(f"Could not verify SSO page identifier '{SSO_PAGE_IDENTIFIER_SPAN_TEXT}' for user {username} at {user_sso_url}. Proceeding with caution.")
        # Optionally, save page source here if this becomes a common issue.
        # with open(f"output/sso_page_source_{username}_debug.html", "w", encoding="utf-8") as f:
        #    f.write(driver.page_source)

    try:
        auth_credentials_heading = WebDriverWait(driver, WAIT_TIMEOUT).until(
            EC.presence_of_element_located((By.XPATH, SSO_AUTHORIZED_CREDENTIALS_SECTION_HEADING_XPATH))
        )
        logging.info(f"Found 'Authorized credentials' section for user {username}.")

        token_row_elements = driver.find_elements(By.CSS_SELECTOR, SSO_TOKEN_ROW_SELECTOR)

        if not token_row_elements:
            logging.warning(f"Found 'Authorized credentials' section for {username}, but no token rows found using selector '{SSO_TOKEN_ROW_SELECTOR}'.")
            debug_filename = SSO_PAGE_SOURCE_DEBUG_PATH.format(username=username)
            try:
                with open(debug_filename, "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                logging.info(f"Saved page source for {username} to {debug_filename} for debugging lack of token rows.")
            except Exception as e_ps:
                logging.error(f"Could not save page source for {username} to {debug_filename}: {e_ps}")
            return []

        logging.info(f"Found {len(token_row_elements)} potential token rows for user {username}.")

        for i, row_element in enumerate(token_row_elements):
            logging.info(f"--- Processing token row {i+1}/{len(token_row_elements)} for user {username} ---")
            token_name = "N/A (Not Found)"
            expiration_date = "N/A (Not Found)"
            try:
                row_html_snippet = row_element.get_attribute('outerHTML')[:700]
                logging.info(f"Row {i+1} HTML snippet for {username}: {row_html_snippet} ...")
            except Exception as e_html:
                logging.warning(f"Could not get HTML for row {i+1} for user {username}: {e_html}")


            try:
                name_element = row_element.find_element(By.CSS_SELECTOR, SSO_TOKEN_NAME_SELECTOR)
                token_name = name_element.text.strip()
                logging.info(f"User {username}, Token {i+1}: Name='{token_name}'")
            except NoSuchElementException:
                logging.warning(f"User {username}, Token {i+1}: Name not found using '{SSO_TOKEN_NAME_SELECTOR}'.")
            except Exception as e_name:
                logging.error(f"User {username}, Token {i+1}: Error extracting name: {e_name}")

            try:
                expiration_element = row_element.find_element(By.CSS_SELECTOR, SSO_TOKEN_EXPIRATION_SELECTOR)
                expiration_date = expiration_element.text.strip()
                logging.info(f"User {username}, Token {i+1}: Expiration='{expiration_date}'")
            except NoSuchElementException:
                logging.warning(f"User {username}, Token {i+1}: Expiration not found using '{SSO_TOKEN_EXPIRATION_SELECTOR}'. May indicate no expiry or different structure.")
            except Exception as e_exp:
                logging.error(f"User {username}, Token {i+1}: Error extracting expiration: {e_exp}")

            if token_name != "N/A (Not Found)":
                user_tokens_data.append({
                    "Username": username,
                    "Token Name": token_name,
                    "Expiration Date": expiration_date
                })
                logging.info(f"User {username}, Token {i+1}: Added to list.")
            else:
                logging.warning(f"User {username}, Token {i+1}: Skipped due to missing token name.")

    except TimeoutException: # This TimeoutException is for the WebDriverWait on SSO_AUTHORIZED_CREDENTIALS_SECTION_HEADING_XPATH
        logging.warning(f"No 'Authorized credentials' section found for user {username} at {user_sso_url} using XPATH '{SSO_AUTHORIZED_CREDENTIALS_SECTION_HEADING_XPATH}'.")
        debug_filename = SSO_PAGE_SOURCE_DEBUG_PATH.format(username=username)
        try:
            with open(debug_filename, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logging.info(f"Saved page source for {username} to {debug_filename} for debugging.")
        except Exception as e_ps:
            logging.error(f"Could not save page source for {username} to {debug_filename}: {e_ps}")
        return []
    except NoSuchElementException:
        # This might occur if an element within a row is not found, but the main try-catch for rows should handle most of it.
        # Or if find_elements for SSO_TOKEN_ROW_SELECTOR somehow fails in an unexpected way (though empty list is handled above).
        logging.warning(f"A 'NoSuchElementException' occurred while processing SSO page for {username}. This might indicate an unexpected structural change or a selector issue deeper in the token row processing. Page source might be helpful.")
        debug_filename = SSO_PAGE_SOURCE_DEBUG_PATH.format(username=username + "_ns_exception") # Differentiate this debug file
        try:
            with open(debug_filename, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            logging.info(f"Saved page source for {username} due to NoSuchElementException to {debug_filename}.")
        except Exception as e_ps:
            logging.error(f"Could not save page source for {username} to {debug_filename}: {e_ps}")
        return []
    except Exception as e:
        logging.error(f"An unexpected error occurred while scraping SSO tokens for user {username} at {user_sso_url}: {e}", exc_info=True)
        # with open(f"output/sso_page_source_error_{username}_debug.html", "w", encoding="utf-8") as f:
        #    f.write(driver.page_source)
        return []

    logging.info(f"Finished scraping SSO tokens for user {username}. Found {len(user_tokens_data)} tokens.")
    return user_tokens_data

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
            # Attempt to find the expiration text using the new selector
            expiration_element = row_element.find_element(By.CSS_SELECTOR, NEW_TOKEN_EXPIRATION_TEXT_SELECTOR)
            expiration_text = expiration_element.text.strip()
            logging.info(f"Row {i+1}: Found expiration text element using '{NEW_TOKEN_EXPIRATION_TEXT_SELECTOR}'. Raw text: '{expiration_text}'")

            if "Expired on " in expiration_text:
                expiration_date_str = expiration_text.split("Expired on ", 1)[1]
                logging.info(f"Row {i+1}: Parsed 'Expired on' date: '{expiration_date_str}'")
            elif "No expiration" in expiration_text: # Example, adjust if GitHub uses different phrasing
                expiration_date_str = "No expiration"
                logging.info(f"Row {i+1}: Parsed 'No expiration'.")
            # Add more elif conditions here if GitHub has other formats like "Expires in X days" that need specific parsing.
            # For now, we capture the raw text if it's not "Expired on " or "No expiration".
            else:
                # If the text is just a date like "May 22, 2025", or "Expires in X days"
                # For this iteration, we'll take the text as is if it's not an "Expired on" format.
                # Future improvements could parse "Expires in X days" to a specific date.
                expiration_date_str = expiration_text
                logging.info(f"Row {i+1}: Using raw expiration text as is (not 'Expired on' or 'No expiration' format): '{expiration_date_str}'")

        except NoSuchElementException:
            logging.warning(f"Row {i+1}: Expiration text element NOT found using selector '{NEW_TOKEN_EXPIRATION_TEXT_SELECTOR}'. This might mean the token has no expiration displayed in this format, or the selector needs an update.")
            # Attempt to find a <relative-time> element as a fallback for "no expiration" or specific dates.
            try:
                relative_time_element = row_element.find_element(By.TAG_NAME, 'relative-time')
                datetime_attr = relative_time_element.get_attribute('datetime')
                if datetime_attr:
                    dt_object = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                    expiration_date_str = dt_object.strftime('%Y-%m-%d')
                    logging.info(f"Row {i+1}: Found expiration date '{expiration_date_str}' using <relative-time> tag's datetime attribute.")
                else:
                    # If <relative-time> exists but has no datetime, check its text.
                    # It might say "No expiration" or similar.
                    relative_time_text = relative_time_element.text.strip()
                    if "no expiration" in relative_time_text.lower(): # Case-insensitive check
                        expiration_date_str = "No expiration"
                        logging.info(f"Row {i+1}: Found 'No expiration' in <relative-time> text: '{relative_time_text}'")
                    else:
                        expiration_date_str = relative_time_text if relative_time_text else "N/A (relative-time text empty)"
                        logging.warning(f"Row {i+1}: <relative-time> tag found but 'datetime' attribute missing and text not recognized as 'no expiration'. Text: '{expiration_date_str}'")
            except NoSuchElementException:
                logging.warning(f"Row {i+1}: Neither '{NEW_TOKEN_EXPIRATION_TEXT_SELECTOR}' nor <relative-time> tag found. Setting expiration to 'N/A (Not Found)'.")
                expiration_date_str = "N/A (Not Found)"
            except Exception as e_rel_time:
                logging.error(f"Row {i+1}: Error processing <relative-time> fallback for token '{token_name}': {e_rel_time}", exc_info=True)
                expiration_date_str = "Error parsing relative-time (see logs)"

        except Exception as e_expiry:
            logging.error(f"Row {i+1}: General error parsing expiration for token '{token_name}' using '{NEW_TOKEN_EXPIRATION_TEXT_SELECTOR}': {e_expiry}", exc_info=True)
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
            fieldnames = ["Username", "Token Name", "Expiration Date"]
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
    logging.info("--- GitHub Organization SSO Token Scraper Initializing ---") # Updated title
    driver = None
    try:
        driver = setup_driver()
        if not check_login_and_navigate(driver): # This now checks for Org People page
            logging.error("Could not verify login or navigate to the Organization People page. Exiting.")
            return

        # New workflow:
        user_sso_urls = get_all_user_sso_links(driver)
        all_sso_tokens_data = []
        logging.info(f"Found {len(user_sso_urls)} user SSO URLs to process.")

        if not user_sso_urls:
            logging.info("No user SSO URLs collected. The script will now exit as there is no data to process.")
        else:
            logging.info(f"Will attempt to scrape SSO tokens for {len(user_sso_urls)} users.")
            for sso_url in user_sso_urls:
                username = "UnknownUser" # Default username
                try:
                    # Extract username from URL like https://github.com/orgs/OrgName/username/sso
                    parts = sso_url.split('/')
                    if len(parts) >= 3 and parts[-1].lower() == 'sso': # basic validation, case-insensitive for 'sso'
                        username = parts[-2]
                    else:
                        logging.warning(f"Could not parse username from SSO URL: {sso_url}. Using default '{username}'.")

                    logging.info(f"--- Scraping SSO page for user: {username} (URL: {sso_url}) ---")
                    tokens_for_user = scrape_sso_tokens_for_user(driver, sso_url, username)

                    if tokens_for_user:
                        all_sso_tokens_data.extend(tokens_for_user)
                        logging.info(f"Successfully scraped {len(tokens_for_user)} token(s) for user: {username}.")
                    else:
                        logging.info(f"No tokens found or scraped for user: {username}.")

                    logging.info(f"Total tokens collected so far: {len(all_sso_tokens_data)}")

                    # Be polite to the server
                    politeness_delay = 1 # seconds
                    logging.debug(f"Waiting for {politeness_delay} second(s) before next user...")
                    time.sleep(politeness_delay)

                except Exception as e_user_loop:
                    logging.error(f"Error processing user SSO URL {sso_url} (User: {username}): {e_user_loop}", exc_info=True)
                    # Optionally, add sso_url to a list of failed URLs to retry later
                    logging.info(f"Skipping to next user due to error with {username}.")
                    continue # Move to the next user

        # The old `scrape_tokens` function is for personal access tokens, not used in this workflow.
        # scraped_tokens = scrape_tokens(driver)

        # Update the CSV fieldnames if they differ for SSO tokens
        # For now, assuming they are "Username", "Token Name", "Expiration Date" as per scrape_sso_tokens_for_user
        logging.info(f"Attempting to save {len(all_sso_tokens_data)} SSO token entries to CSV.")
        save_to_csv(all_sso_tokens_data, OUTPUT_FILE)

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
