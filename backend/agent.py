# Prima di eseguire questo script, assicurati di installare le librerie necessarie:
# pip install google-generativeai pypdf docx2txt openpyxl unstructured python-pptx

import os
import asyncio
import google.generativeai as genai
import PyPDF2
import docx2txt
from unstructured.partition.xlsx import partition_xlsx
from pptx import Presentation

# Configurazione Gemini
GOOGLE_API_KEY = "AIzaSyASlsh1jRxd2iZnM3E3FM1TlDZ4yarUUMU"
genai.configure(api_key=GOOGLE_API_KEY)

# Configurazione del modello
model = genai.GenerativeModel('gemini-2.0-flash')

async def extract_text_from_docx(file_path):
    """Estrae il testo da un file DOCX."""
    try:
        text = docx2txt.process(file_path)
        return text
    except Exception as e:
        print(f"Errore nell'estrazione del testo da DOCX: {e}")
        return None

async def extract_text_from_pdf(file_path):
    """Estrae il testo da un file PDF."""
    try:
        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        print(f"Errore nell'estrazione del testo da PDF: {e}")
        return None

async def extract_text_from_xlsx(file_path):
    """Estrae il testo da un file XLSX."""
    try:
        elements = partition_xlsx(file_path)
        text = "\n".join([str(element) for element in elements])
        return text
    except Exception as e:
        print(f"Errore nell'estrazione del testo da XLSX: {e}")
        return None

async def extract_text_from_pptx(file_path):
    """Estrae il testo da un file PowerPoint."""
    try:
        prs = Presentation(file_path)
        text = []
        
        # Estrai testo da ogni slide
        for slide in prs.slides:
            slide_text = []
            # Estrai testo dai placeholder
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    slide_text.append(shape.text)
            # Aggiungi il testo della slide alla lista
            if slide_text:
                text.append("\n".join(slide_text))
        
        return "\n\n".join(text)
    except Exception as e:
        print(f"Error extracting text from PPTX: {e}")
        return None

async def get_document_text(file_path):
    """Estrae il testo dal documento in base al suo tipo."""
    _, file_extension = os.path.splitext(file_path)
    
    if file_extension.lower() == '.docx':
        return await extract_text_from_docx(file_path)
    elif file_extension.lower() == '.pdf':
        return await extract_text_from_pdf(file_path)
    elif file_extension.lower() in ['.xlsx', '.xls']:
        return await extract_text_from_xlsx(file_path)
    elif file_extension.lower() == '.pptx':
        return await extract_text_from_pptx(file_path)
    else:
        print(f"Unsupported file format: {file_extension}")
        return None

async def summarize_text(text, file_type):
    """Genera un riassunto del testo usando Gemini con un prompt specifico per il tipo di file."""
    try:
        # Prompt specifici per tipo di file
        prompts = {
            '.docx': """Provide a comprehensive and detailed analysis of the following Word document. 
            Your summary should be a continuous, flowing text that:
            - Begins with a brief overview of the document's main purpose and scope
            - Breaks down the content into key sections and themes
            - Highlights important arguments, findings, or conclusions
            - Includes specific examples or data points that support the main points
            - Maintains the logical flow and structure of the original document
            - Ends with a list of the most significant keywords and terms used in the document

            Write the summary as a continuous text without any numbered sections or bullet points.

            DOCUMENT TEXT:
            {text}

            SUMMARY:""",

            '.pdf': """Provide a comprehensive and detailed analysis of the following PDF document. 
            Your summary should be a continuous, flowing text that:
            - Starts with a clear overview of the document's purpose and scope
            - Analyzes both the content and structural elements
            - Identifies and explains key sections, chapters, or topics
            - Includes relevant data, statistics, or findings
            - Highlights any visual elements or formatting that contribute to the content
            - Ends with a list of the most significant keywords and terms used in the document

            Write the summary as a continuous text without any numbered sections or bullet points.

            PDF TEXT:
            {text}

            SUMMARY:""",

            '.xlsx': """Provide a comprehensive and detailed analysis of the following Excel spreadsheet. 
            Your summary should be a continuous, flowing text that:
            - Begins with an overview of the spreadsheet's purpose and structure
            - Identifies and explains all major data categories and their relationships
            - Highlights key trends, patterns, or anomalies in the data
            - Includes specific numerical values, percentages, or statistics that are significant
            - Analyzes any formulas or calculations present in the data
            - Identifies any correlations or dependencies between different data points
            - Summarizes the main findings or insights from the data
            - Ends with a list of the most significant keywords, terms, and data categories used in the spreadsheet

            Write the summary as a continuous text without any numbered sections or bullet points.

            SPREADSHEET CONTENT:
            {text}

            SUMMARY:""",

            '.pptx': """Provide a comprehensive and detailed analysis of the following PowerPoint presentation. 
            Your summary should be a continuous, flowing text that:
            - Starts with an overview of the presentation's main objective and target audience
            - Breaks down the content slide by slide, highlighting key messages
            - Analyzes the flow and progression of ideas throughout the presentation
            - Identifies and explains any visual elements or design choices mentioned in the text
            - Highlights important data points, statistics, or examples used
            - Notes any transitions or connections between different topics
            - Ends with a list of the most significant keywords and terms used in the presentation

            Write the summary as a continuous text without any numbered sections or bullet points.

            PRESENTATION TEXT:
            {text}

            SUMMARY:"""
        }

        # Seleziona il prompt appropriato o usa quello di default
        prompt_template = prompts.get(file_type.lower(), """Provide a comprehensive and detailed analysis of the following text. 
            Your summary should be a continuous, flowing text that:
            - Begins with a clear overview of the content's main purpose
            - Breaks down the information into key sections and themes
            - Includes specific details, examples, or data points
            - Maintains the logical flow of the original text
            - Ends with a list of the most significant keywords and terms used

            Write the summary as a continuous text without any numbered sections or bullet points.

            TEXT TO SUMMARIZE:
            {text}

            SUMMARY:""")

        prompt = prompt_template.format(text=text)
        
        response = await asyncio.to_thread(
            model.generate_content,
            prompt
        )
        
        return response.text
    except Exception as e:
        print(f"Error during summary generation: {e}")
        return None

async def summarize_document(file_path: str) -> str:
    """Carica e riassume un documento."""
    if not os.path.exists(file_path):
        return f"Error: File {file_path} does not exist."

    print(f"Loading document: {file_path}...")
    text = await get_document_text(file_path)
    
    if not text:
        return "Unable to extract text from the document."

    print("Generating summary...")
    _, file_extension = os.path.splitext(file_path)
    summary = await summarize_text(text, file_extension)
    
    if not summary:
        return "Error during summary generation."

    return summary

async def main():
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python agent.py <file_path>")
        print("Supported formats: .docx, .pdf, .xlsx, .pptx")
        return

    file_path = sys.argv[1]
    summary = await summarize_document(file_path)
    
    print("\nFINAL SUMMARY:")
    print(summary)
    print("-" * 30)

if __name__ == "__main__":
    asyncio.run(main())