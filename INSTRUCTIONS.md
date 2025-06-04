# GitHub Classic PAT Scraper - Instructions

This document provides comprehensive instructions for setting up, using, and understanding the GitHub Classic PAT Scraper. This tool is designed to help you identify your classic Personal Access Tokens (PATs) on GitHub.

**Target Audience:** This guide is written for users who need to run the scraper, including those with novice programming experience.

## Table of Contents
1.  [Project Overview](#1-project-overview)
    * [Purpose](#purpose)
    * [Why Scrape Classic PATs?](#why-scrape-classic-pats)
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
7.  [Developer Guidelines](#7-developer-guidelines)
    * [Code Style and Documentation](#code-style-and-documentation)
    * [Git Version Control](#git-version-control)
    * [Dependency Management](#dependency-management)
    * [Handling Scraper Changes (CSS Selectors)](#handling-scraper-changes-css-selectors)
    * [Security Best Practices for PATs](#security-best-practices-for-pats)
8.  [Troubleshooting](#8-troubleshooting)
9.  [Disclaimer](#9-disclaimer)

---

## 1. Project Overview

### Purpose
The GitHub Classic PAT Scraper is a Python tool that automates the process of listing all "Personal access tokens (classic)" from your GitHub account settings page (`https://github.com/settings/tokens`). The output is a CSV file containing the token names and their expiration dates.

### Why Scrape Classic PATs?
Classic PATs on GitHub have broad permissions and lack the fine-grained control offered by newer Fine-grained PATs or GitHub Apps. They can pose a security risk if compromised or if they have overly permissive scopes or no expiration. Identifying these tokens is the first step towards migrating to more secure alternatives or ensuring existing classic PATs are appropriately managed (e.g., by adding expirations, reducing scopes, or deleting them if unused).

**This script is for individual use to check your *own* tokens.** It is not designed for organization-wide admin-level auditing of all users' PATs.

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
cd <repository_name> # e.g., cd github_pat_scraper