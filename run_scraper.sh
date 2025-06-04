#!/bin/bash
# run_scraper.sh
# This script sets up the Python virtual environment, installs dependencies,
# and runs the PAT scraper.

# --- Configuration ---
PYTHON_EXEC="python3" # Change to "python" if python3 isn't your command for Python 3
VENV_NAME="venv"
REQUIREMENTS_FILE="requirements.txt"
PYTHON_SCRIPT="src/scraper.py"
LOG_DIR="logs"
AUDIT_LOG_FILE="${LOG_DIR}/dependency_audit.log"

# --- Functions ---
log_audit() {
    # Appends a timestamped message to the audit log file.
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" >> "${AUDIT_LOG_FILE}"
}

check_command_exists() {
    # Checks if a command exists and is executable.
    # $1: The command to check (e.g., "python3", "git").
    if ! command -v "$1" &> /dev/null; then
        echo "❌ Error: Command '$1' not found. Please install it."
        log_audit "Error: Command '$1' not found."
        exit 1
    fi
    echo "✅ Command '$1' found."
    log_audit "Command '$1' found."
}

# --- Main Script ---
echo "🚀 Starting GitHub PAT Scraper Execution..."

# Create log directory if it doesn't exist
mkdir -p "${LOG_DIR}"
echo "📝 Audit log will be written to: ${AUDIT_LOG_FILE}"
log_audit "Script run_scraper.sh started."

# 1. Check for Python 3
echo "🔎 Checking for Python 3 ('${PYTHON_EXEC}')..."
check_command_exists "${PYTHON_EXEC}"

# 2. Check for pip availability via Python
echo "🔎 Checking for pip availability via '${PYTHON_EXEC} -m pip'..."
if ! "${PYTHON_EXEC}" -m pip --version &> /dev/null; then
    echo "❌ Error: '${PYTHON_EXEC} -m pip --version' failed or pip is not available."
    echo "   This means Python cannot find its package manager (pip)."
    echo "   Common solutions:"
    echo "     - Ensure Python 3 is fully installed (e.g., 'sudo apt install python3-pip python3-venv' on Debian/Ubuntu)."
    echo "     - If using a custom Python build, ensure pip was included or install it for that specific Python."
    log_audit "Error: '${PYTHON_EXEC} -m pip --version' failed."
    exit 1
fi
echo "✅ '${PYTHON_EXEC} -m pip' is available."
log_audit "'${PYTHON_EXEC} -m pip' is available."

# 3. Setup Python Virtual Environment
echo "🐍 Setting up Python virtual environment '${VENV_NAME}'..."
if [ ! -d "${VENV_NAME}" ]; then
    echo "   Creating virtual environment..."
    "${PYTHON_EXEC}" -m venv "${VENV_NAME}"
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment. Please check your Python installation and ensure the 'venv' module is available."
        log_audit "Error: Failed to create virtual environment."
        exit 1
    fi
    log_audit "Virtual environment '${VENV_NAME}' created."
    echo "   ✅ Virtual environment created."
else
    echo "   🐍 Virtual environment '${VENV_NAME}' already exists."
    log_audit "Virtual environment '${VENV_NAME}' already exists."
fi

# 4. Activate Virtual Environment and Install Dependencies
echo "⚙️ Activating virtual environment and installing/updating dependencies from ${REQUIREMENTS_FILE}..."
source "${VENV_NAME}/bin/activate"
if [ $? -ne 0 ]; then
    echo "❌ Failed to activate virtual environment. Ensure it was created successfully."
    log_audit "Error: Failed to activate virtual environment."
    exit 1
fi
log_audit "Virtual environment activated."

echo "   Installing/Updating pip..."
"${PYTHON_EXEC}" -m pip install --upgrade pip >> "${AUDIT_LOG_FILE}" 2>&1
if [ $? -ne 0 ]; then
    echo "⚠️ Warning: Failed to upgrade pip. Continuing with existing version. Check ${AUDIT_LOG_FILE} for details."
    log_audit "Warning: Failed to upgrade pip."
fi

echo "   Installing dependencies from ${REQUIREMENTS_FILE}..."
"${PYTHON_EXEC}" -m pip install -r "${REQUIREMENTS_FILE}" >> "${AUDIT_LOG_FILE}" 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Failed to install dependencies. Check ${AUDIT_LOG_FILE} for details."
    log_audit "Error: Failed to install dependencies from ${REQUIREMENTS_FILE}."
    # Deactivate venv before exiting on error
    deactivate
    exit 1
fi
echo "   ✅ Dependencies installed/updated successfully."
log_audit "Dependencies installed/updated from ${REQUIREMENTS_FILE}."

# 5. Run the Python Scraper
echo "▶️ Running the Python scraper (${PYTHON_SCRIPT})..."
"${PYTHON_EXEC}" "${PYTHON_SCRIPT}"
SCRIPT_EXIT_CODE=$? # Capture exit code of the Python script

if [ ${SCRIPT_EXIT_CODE} -ne 0 ]; then
    echo "❌ Python script exited with an error (code: ${SCRIPT_EXIT_CODE}). Check script logs in '${LOG_DIR}/scraper.log'."
    log_audit "Error: Python script ${PYTHON_SCRIPT} exited with error code ${SCRIPT_EXIT_CODE}."
else
    echo "✅ Python script finished successfully."
    log_audit "Python script ${PYTHON_SCRIPT} finished successfully."
fi

# 6. Deactivate Virtual Environment
echo "🔌 Deactivating virtual environment."
deactivate
log_audit "Virtual environment deactivated."

echo "🎉 GitHub PAT Scraper Execution Complete."
log_audit "Script run_scraper.sh finished."

# Exit with the Python script's exit code to reflect its success/failure
exit ${SCRIPT_EXIT_CODE}
