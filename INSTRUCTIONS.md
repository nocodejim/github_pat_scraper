# GitHub Organization SSO Token Scraper - Instructions

This document provides comprehensive instructions for setting up, using, and understanding the GitHub Organization SSO Token Scraper. This tool is designed to help you identify and list Authorized SSO credentials (tokens) for users within a specified GitHub organization.

**Target Audience:** This guide is written for users who need to run the scraper, including those with novice programming experience, and administrators or security personnel authorized to audit organization SSO tokens.

## Table of Contents
1.  [Project Overview](#1-project-overview)
    * [Purpose](#purpose)
    * [Why Audit SSO Tokens?](#why-audit-sso-tokens)
    * [Technology Stack](#technology-stack)
2.  [Prerequisites](#2-prerequisites)
3.  [Setup Instructions](#3-setup-instructions)
    * [Step 1: Get the Project Files](#step-1-get-the-project-files)
    * [Step 2: Run the Project Setup Script](#step-2-run-the-project-setup-script)
4.  [Running the Scraper](#4-running-the-scraper)
    * [How it Works](#how-it-works)
    * [Executing the Run Script](#executing-the-run-script)
    * [Manual Login (If Required)](#manual-login-if-required)
5.  [Output](#5-output)
    * [CSV Report](#csv-report)
    * [Logs](#logs)
6.  [Understanding the Code & Concepts](#6-understanding-the-code--concepts)
    * [Project Structure](#project-structure)
    * [Python and `venv` (Virtual Environments)](#python-and-venv-virtual-environments)
    * [Key Python Libraries](#key-python-libraries)
    * [Web Scraping with Selenium](#web-scraping-with-selenium)
7.  [Troubleshooting and Developer Guidelines](#7-troubleshooting-and-developer-guidelines)
    * [Refining CSS Selectors for SSO Tokens](#refining-css-selectors-for-sso-tokens)
    * [Code Style and Documentation](#code-style-and-documentation)
    * [Git Version Control](#git-version-control)
    * [Dependency Management](#dependency-management)
    * [Security Best Practices for Credentials](#security-best-practices-for-credentials)
8.  [Disclaimer](#8-disclaimer)

---

## 1. Project Overview

### Purpose
The GitHub Organization SSO Token Scraper is a Python tool that automates the process of identifying and listing Authorized SSO credentials (tokens) for users within a specified GitHub organization. It navigates to the organization's people pages, then to each user's SSO identity page, and attempts to extract token details. The primary target organization is 'Cincinnati-Insurance' by default. The output is a CSV file containing the username, token name, and expiration date.

### Why Audit SSO Tokens?
Auditing SSO tokens across an organization is crucial for security and compliance. These tokens can grant access to organizational resources. Understanding which users have authorized what credentials, and when these expire (or if they don't), helps in identifying potential security risks, ensuring adherence to token lifecycle policies, and maintaining an inventory of active credentials linked via SSO.

### Technology Stack
* **Python 3**: The programming language used for the scraper.
* **Selenium**: A browser automation framework. It controls a web browser (Chrome, in this case) to navigate web pages and extract information, especially from pages that require login or use JavaScript.
* **webdriver-manager**: A Python library that helps to automatically download and manage the browser drivers (like `chromedriver`) required by Selenium.
* **Bash Shell Scripts**: Used for project setup and running the application.
* **Git**: For version control (the project is set up as a Git repository).

---

## 2. Prerequisites

Before you begin, ensure you have the following installed on your system (specifically within your WSL environment if you are using Windows Subsystem for Linux):

1.  **WSL (Ubuntu 24.04 or similar)**: As per your setup.
2.  **Git**: To clone or manage the project. Install via `sudo apt update && sudo apt install git`.
3.  **Python 3.8+**: Check with `python3 --version`. Install via `sudo apt install python3 python3-pip python3-venv`.
4.  **pip (Python package installer)**: Usually comes with Python 3. Check with `pip3 --version`.
5.  **Google Chrome Browser**: The script uses Chrome. It should be installed on your host Windows system if running WSL, or within WSL if you have a graphical environment set up (the former is simpler for this script). The script will attempt to interact with Chrome installed on Windows.

---

## 3. Setup Instructions

### Step 1: Get the Project Files
If you received this as a set of files, ensure they are all in a single directory. If it's a Git repository you need to clone:
```bash
git clone <repository_url>
cd <repository_name> # e.g., cd github_sso_scraper
```
Ensure all provided files (`src/scraper.py`, `run_scraper.sh`, `setup_project.sh`, `requirements.txt`, `INSTRUCTIONS.md`, etc.) are present.

### Step 2: Run the Project Setup Script
This script creates a Python virtual environment and installs the necessary packages.
```bash
bash setup_project.sh
```
This will:
1. Create a directory named `venv` for the virtual environment.
2. Activate the virtual environment.
3. Install Python packages listed in `requirements.txt` (like Selenium and webdriver-manager) into `venv`.

You only need to run `setup_project.sh` once. If you pull updates that change `requirements.txt`, you might need to re-run it or manually install new dependencies.

---

## 4. Running the Scraper

### How it Works
1.  The script starts by navigating to the GitHub organization's 'people' page (default: `https://github.com/orgs/Cincinnati-Insurance/people`).
2.  It requires you to be logged into an account that has permission to view this organization's members and their SSO settings. You might be prompted to log in directly in the browser window opened by Selenium.
3.  It iterates through all pages of users listed for the organization.
4.  For each user found, it constructs a URL to their SSO identity page (e.g., `https://github.com/orgs/Cincinnati-Insurance/USERNAME/sso`).
5.  It navigates to this SSO page and looks for a section titled 'Authorized credentials'.
6.  If this section and specific token elements are found (using CSS selectors like `div.Box-row.d-flex.flex-column.token-type`), it extracts the token name and its expiration date.
7.  All collected data (username, token name, expiration date) is compiled.

### Executing the Run Script
To start the scraper:
```bash
bash run_scraper.sh
```
This script will:
1. Activate the Python virtual environment (if not already active).
2. Execute the `src/scraper.py` Python script.
3. A Chrome browser window will open, controlled by Selenium.

**Important:** Do not close the automated Chrome window or interact with it unless prompted for login. The script needs it to work.

### Manual Login (If Required)
*   The script will first attempt to navigate to the organization's people page.
*   If you are not logged into GitHub in the browser session that Selenium opens, or if your session doesn't have the necessary permissions, you will likely be redirected to a GitHub login page or an error page.
*   **Action:** Manually log in using the Selenium-controlled browser window. Use an account that has **permission to view the target organization's members and their SSO settings page**.
*   Once you have successfully logged in and navigated to the organization's people page (e.g., `https://github.com/orgs/Cincinnati-Insurance/people`), the script will attempt to detect this and continue.
*   The script has a timeout for this manual login step. If it cannot detect the target page after login within a few minutes, it will terminate.

---

## 5. Output

### CSV Report
The primary output is a CSV file (default: `output/org_sso_tokens_report.csv`). This file will contain the following columns:
*   `Username`: The GitHub username of the organization member.
*   `Token Name`: The name or description of the authorized SSO credential.
*   `Expiration Date`: The expiration date of the token, if available. If not found or not applicable, it might say "N/A (Not Found)" or similar.

An empty CSV file (with only headers) will be created if no tokens are found or if an error occurs before data collection.

### Logs
*   **`logs/scraper.log`**: This file contains detailed logs of the script's execution, including informational messages, warnings (e.g., if a user has no SSO tokens), and any errors encountered. Check this file first if the script doesn't behave as expected.
*   **Debug HTML Dumps**: Additionally, if the scraper encounters issues finding expected sections or token details on a user's SSO page, it may save the HTML source of that page to a file like `output/debug_sso_page_source_{username}.html`. These files are crucial for troubleshooting, especially for refining CSS selectors (see 'Refining CSS Selectors for SSO Tokens' below).

---

## 6. Understanding the Code & Concepts

### Project Structure
```
.
├── src/
│   └── scraper.py        # Main Python script for scraping
├── output/                 # Directory for CSV reports and debug files (created on run)
├── logs/                   # Directory for log files (created on run)
├── venv/                   # Python virtual environment (created by setup script)
├── run_scraper.sh          # Shell script to run the scraper
├── setup_project.sh        # Shell script for initial project setup
├── requirements.txt        # Python package dependencies
└── INSTRUCTIONS.md         # This file
```

### Python and `venv` (Virtual Environments)
Python projects often use virtual environments (`venv`) to manage dependencies. A `venv` isolates the packages used for one project from others on your system. This avoids conflicts if different projects need different versions of the same library. The `setup_project.sh` script creates and manages this.

### Key Python Libraries
*   **`selenium`**: For browser automation and web scraping.
*   **`webdriver-manager`**: Handles downloading the correct `chromedriver`.
*   **`csv`**: For writing data to the CSV file.
*   **`logging`**: For creating informative log messages.
*   **`time`**: Used for adding delays (e.g., `time.sleep()`) to make the script more stable or polite to the server.
*   **`os`**: Used for file system operations like creating directories.

### Web Scraping with Selenium
Selenium works by:
1.  Starting a web browser (like Chrome).
2.  Loading a specific URL.
3.  Finding HTML elements on the page using "selectors" (like CSS selectors or XPath).
4.  Extracting data (text, attributes) from these elements.
5.  Interacting with elements (clicking buttons, filling forms - though this script mainly extracts data).

Since web pages can change their structure, the selectors might occasionally need updates.

---

## 7. Troubleshooting and Developer Guidelines

### Refining CSS Selectors for SSO Tokens
GitHub's website structure can change over time, which may break the CSS selectors used by the scraper to find information. If the script runs but doesn't find any tokens for users who should have them, or if you see warnings in the logs about missing elements (like "No 'Authorized credentials' section found" or "No token rows found"), you may need to update these selectors.

**Key Selectors to Check (defined in `src/scraper.py`):**
*   `ORG_PEOPLE_PAGE_IDENTIFIER_XPATH`: Identifies the main "People" page of the organization.
*   `USER_PROFILE_LINK_SELECTOR`: Finds links to individual user profiles on the "People" page.
*   `PAGINATION_NEXT_BUTTON_SELECTOR`: Finds the "Next" button to go to the next page of users.
*   `SSO_PAGE_IDENTIFIER_SPAN_TEXT` (used in an XPATH): Verifies the script is on a user's SSO settings page.
*   `SSO_AUTHORIZED_CREDENTIALS_SECTION_HEADING_XPATH`: Locates the "Authorized credentials" heading on the SSO page. This is crucial.
*   `SSO_TOKEN_ROW_SELECTOR`: (Critical for finding any tokens) Selects each row representing an authorized token.
*   `SSO_TOKEN_NAME_SELECTOR`: (For the token's name/description) Extracts the token's name from within a row.
*   `SSO_TOKEN_EXPIRATION_SELECTOR`: (For the token's expiration) Extracts the token's expiration information from within a row.

**Debugging Steps:**
1.  **Check the Logs:** The `logs/scraper.log` file provides detailed information about the script's execution, including warnings if elements are not found and often the specific selector that failed.
2.  **Inspect Saved HTML Pages:** If the script saved files like `output/debug_sso_page_source_{username}.html`, open these in a web browser. These are snapshots of what the scraper saw when it failed to find an element. This is the most direct way to see the page structure the script is dealing with.
3.  **Use Browser Developer Tools:** On the live GitHub page (navigate there manually if needed, or use one of the saved HTML debug files), right-click the element you're interested in (e.g., a token name, the "Authorized credentials" heading) and select 'Inspect' or 'Inspect Element'. This will open the developer tools and highlight the HTML code for that element.
4.  **Identify New Selectors:**
    *   Look for unique attributes like `id`, `class`, or a combination of HTML tags and attributes that can reliably identify the target element.
    *   Examine the structure. Is the element you want a child of another specific element? This can help make selectors more precise.
    *   You can right-click the HTML element in the developer tools and often find options like 'Copy > Copy selector' or 'Copy > Copy XPath'. These can be good starting points, but sometimes need simplification or adjustment for robustness.
5.  **Test Selectors:** In the browser's developer console:
    *   For CSS selectors: `document.querySelectorAll('YOUR_NEW_SELECTOR_HERE')`. This should return a list of elements. Check if it finds what you expect.
    *   For XPath: `$x('YOUR_NEW_XPATH_HERE')`.
6.  **Update `src/scraper.py`:** Once you've found working selectors, update the corresponding constant values at the top of the `src/scraper.py` file.

**Note on HTML Snippets:** The scraper logs HTML snippets for rows being processed or when specific sub-elements (like token name or expiration) are not found within a row. These snippets are invaluable for pinpointing issues with `SSO_TOKEN_NAME_SELECTOR` or `SSO_TOKEN_EXPIRATION_SELECTOR` without needing the full page source, although the full source is better if available.

### Code Style and Documentation
*   Follow PEP 8 guidelines for Python code.
*   Write clear comments and docstrings (especially for functions).

### Git Version Control
*   Commit changes with clear, descriptive messages.
*   Use branches for new features or significant fixes.

### Dependency Management
*   Keep `requirements.txt` updated. If you add a new library, freeze it: `pip freeze > requirements.txt` (after activating the `venv`).

### Security Best Practices for Credentials
*   **Principle of Least Privilege**: Ensure any credentials (like PATs, if you were using them for API access, which this script doesn't directly do but is related) have only the minimum necessary permissions.
*   **Regular Audits**: Regularly review authorized SSO credentials and other access tokens. This script helps with that for SSO tokens.
*   **Expiration Dates**: Enforce expiration dates on tokens whenever possible.
*   **Secure Storage**: If you were to handle tokens directly, store them securely (e.g., using a secrets manager, not hardcoded in scripts). This script *reports* on tokens, it doesn't create or store them itself.
*   **Revocation**: Promptly revoke any tokens that are compromised, no longer needed, or belong to users who have left the organization.

---

## 8. Disclaimer

This tool interacts with the GitHub website. GitHub may update its website structure or change its terms of service at any time, which could affect the functionality of this script. The user of this script is responsible for ensuring compliance with GitHub's terms of service and any applicable laws or regulations. The developers of this script are not responsible for any misuse or unintended consequences of using this tool. Use with caution and ensure you have the appropriate permissions to access the organization's data you are targeting.
