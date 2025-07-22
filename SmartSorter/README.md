# SmartSorter

AI-powered file sorter that uses a local LLM via Ollama to categorize files based on their content and sort them into relevant folders.

## Features

- **AI-Powered Categorization**: Leverages local large language models (LLMs) through Ollama to analyze file content and assign a relevant category.
- **Broad File Support**: Extracts text from various file formats, including:
    - PDF (`.pdf`)
    - Word Documents (`.docx`)
    - Excel Spreadsheets (`.xlsx`)
    - Images (`.png`, `.jpg`, `.jpeg`) via OCR
- **Interactive Preview & Editing**: Before any files are moved, a detailed preview window is displayed where you can:
    - **Review the Sorting Plan**: See which category was assigned to each file.
    - **Manually Change Categories**: Right-click any file to assign a different category.
    - **Exclude Files**: Right-click and choose "Exclude from sorting" to keep a file in its original location.
    - **Sort and Organize**: Click on any column header (File, Type, Size, Category) to sort the plan and make it easier to review.
- **Simple GUI**: An intuitive graphical interface to select source/target folders and the desired Ollama model.
- **CLI Mode**: A command-line interface is also available for scripting and automation.

## How It Works

1.  **Select Folders**: Choose a source folder containing the files you want to sort and a target folder where the categorized subdirectories will be created.
2.  **Choose a Model**: Select an available Ollama model for the analysis.
3.  **Analyze**: The sorter extracts text from each supported file and sends it to the LLM with a prompt asking it to choose the best category from a predefined list.
4.  **Review & Edit**: The interactive preview window appears with the full sorting plan. You can make any necessary adjustments here.
5.  **Apply**: Once you approve the plan, the files are moved into their new, organized subfolders.

## Requirements

- Python 3.7+
- An Ollama server with at least one model installed (e.g., `ollama pull phi3`).
- Tesseract OCR engine for image-to-text extraction.

This tool is designed to bring powerful, local AI capabilities to the everyday task of file organization.
