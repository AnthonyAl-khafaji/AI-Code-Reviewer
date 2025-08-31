# CSI 3370 - Capstone Project (AI Code Reviewer)

This project is an AI-powered code reviewer built using a Python Flask backend and a React frontend. The application allows users to paste code for automated analysis (linting, complexity, and security) and chat with an AI assistant about improvements, bugs, or suggestions.

## Features

- Static analysis with:

  - Ruff (linting & style issues)

- **Radon** (maintainability index & complexity metrics)

- **Bandit** (security checks)

- AI-generated scores for readability, complexity, security, and testing

- Actionable suggestions based on results

- Integrated chat panel powered by Ollama (local) or OpenAI API

- Clean, two-column UI (Code Reviewer ↔ Chat) built in React

## Requirements

- Python 3.10 or higher

- Node.js and npm

- Flask and necessary Python packages (pip install -r requirements.txt)

- (Optional) Ollama for free local AI

- (Optional) OpenAI API key

## Interaction

- Paste Python code into the Code Reviewer panel

- The app will display:

- **Summary** (maintainability index, cyclomatic complexity, lint, and security findings)

- **Scores** (readability, complexity, security, testing)

- **Issues list** (lint, syntax, security)

- **Actionable suggestions**

- Use the Chat panel to ask AI about your code, errors, or improvements

| How to Run |
| ---------- |
| **__Step 1: Backend Setup__**
Open a terminal in the backend folder via cd backend.
Create and activate a virtual environment:
python -m venv venv
.\venv\Scripts\activate (Windows) or source venv/bin/activate (Mac/Linux).
Install requirements: pip install -r requirements.txt.
Run the backend: python app.py.
The backend will start on http://localhost:5001.

| **__Step 2: Frontend Setup__**
Open a terminal in the frontend folder via cd frontend.
Install dependencies: npm install.
Run the frontend: npm run dev.
The frontend will start on http://localhost:5173 and open in your browser.

| **__Step 3: (Optional) AI Setup__**
For Ollama (local AI):
ollama pull llama3.2:3b
ollama serve.
For OpenAI:
Set your key with setx OPENAI_API_KEY "your_api_key_here".

| To view the demos included in this repository |
| ---------- |
Navigate to the demo file in the repo.
Click on the file name to open its preview page.
Click the “View raw” button.
The demo will begin downloading automatically.

## Contributor
- Anthony Al-khafaji @AnthonyAl-khafaji
