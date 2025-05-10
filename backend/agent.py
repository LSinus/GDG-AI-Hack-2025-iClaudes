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
            '.docx': """PYou are an Expert Document Summarizer and Analyst. Your task is to create a comprehensive, detailed, and faithful summary of the following text, which has been extracted from a Word document (`.docx`).

            The summary you generate is critically important: it will serve as the primary reference point (representing an older version of the document) for a subsequent AI-driven comparison against a newer version. The goal of that future comparison is to determine if significant content changes, thematic shifts, or semantic differences have occurred. Therefore, your summary must be rich in detail, accurately reflect the core content of the Word document, and meticulously identify key concepts.

            Given that the text originates from a `.docx` file, expect content that may include structured narrative, reports, articles, or other textual forms. Pay attention to the document's inherent structure, such as sections, arguments, and findings.

            Please structure your output as follows:

            1.  **Main Summary (Continuous Text):**
            * Begin with a concise overview that clearly states the Word document's main purpose, overall scope, and primary objectives as evident from the provided text.
            * Thoroughly identify and elaborate on the key sections, principal themes, and core arguments presented in the text.
            * Extract and integrate important specific details, data points, critical findings, illustrative examples, or key conclusions that substantiate the main themes. Your summary should be factual and well-supported by the source text.
            * While maintaining a continuous, flowing narrative (without numbered lists or bullet points in this section), try to preserve the logical progression of ideas and the structural essence of the original document if it is discernible from the text.

            2.  **Keywords (Formatted List - Crucial for Comparison):**
            * The summary *must* conclude with a list of the most significant and representative keywords and key terms/phrases extracted from the document.
            * This list is vital for the subsequent comparison process. Choose keywords that truly encapsulate the core topics, unique identifiers, and essential semantic anchors of the document's content.
            * Format this list *exactly* as follows, on a new line after the main summary:
                `KEYWORDS: keyword1, keyword2, keyword3, term phrase 4, ...`

            ***IMPORTANT: DO NOT include this character in your response: ` ***

            DOCUMENT TEXT (from .docx):
            {text}

            SUMMARY:""",

            '.pdf': """You are an Expert Document Summarizer and Analyst. Your task is to create a comprehensive, detailed, and faithful summary of the following text, which has been extracted from a PDF document (`.pdf`).

            The summary you generate is critically important: it will serve as the primary reference point (representing an older version of the document) for a subsequent AI-driven comparison against a newer version. The goal of that future comparison is to determine if significant content changes, thematic shifts, or semantic differences have occurred. Therefore, your summary must be rich in detail, accurately reflect the core content of the PDF, and meticulously identify key concepts.

            Given that the text originates from a `.pdf` file, be aware that the content could range from formal reports and articles to brochures or scanned documents. Focus on extracting the substantive textual information, identifying structural elements like chapters or sections if evident, and noting any textual descriptions of significant visual elements (e.g., charts, tables) if they are part of the extracted text.

            Please structure your output as follows:

            1.  **Main Summary (Continuous Text):**
                * Begin with a concise overview that clearly states the PDF document's main purpose, overall scope, and primary objectives as evident from the provided text.
                * Thoroughly identify and elaborate on the key sections, principal themes, and core arguments presented in the text.
                * Extract and integrate important specific details, data points, critical findings, illustrative examples, or key conclusions that substantiate the main themes. Your summary should be factual and well-supported by the source text.
                * While maintaining a continuous, flowing narrative (without numbered lists or bullet points in this section), try to preserve the logical progression of ideas and the structural essence of the original document if it is discernible from the text.

            2.  **Keywords (Formatted List - Crucial for Comparison):**
                * The summary *must* conclude with a list of the most significant and representative keywords and key terms/phrases extracted from the document.
                * This list is vital for the subsequent comparison process. Choose keywords that truly encapsulate the core topics, unique identifiers, and essential semantic anchors of the document's content.
                * Format this list *exactly* as follows, on a new line after the main summary:
                    `KEYWORDS: keyword1, keyword2, keyword3, term phrase 4, ...`

            ***IMPORTANT: DO NOT include this character in your response: ` ***

            PDF DOCUMENT TEXT (from .pdf):
            {text}

            SUMMARY:""",

            '.xlsx': """You are an Expert Document Summarizer and Analyst. Your task is to create a comprehensive, detailed, and faithful summary of the following text, which represents content extracted from an Excel spreadsheet (`.xlsx`).

            The summary you generate is critically important: it will serve as the primary reference point (representing an older version of the spreadsheet) for a subsequent AI-driven comparison against a newer version. The goal of that future comparison is to determine if significant content changes, thematic shifts, or semantic differences have occurred in the data or its interpretation. Therefore, your summary must accurately capture the essence of the spreadsheet's data, structure, and any discernible insights.

            Given that the text originates from an `.xlsx` file, expect data that might be tabular, lists of values, or textual descriptions of cell contents and sheet structures. Your primary focus should be on interpreting this data textually.

            Please structure your output as follows:

            1.  **Main Summary (Continuous Text):**
                * Begin with an overview of the spreadsheet's apparent purpose and how the data is broadly structured, based on the provided text.
                * Identify and explain major data categories, variables, and their relationships if discernible from the textual representation.
                * Highlight key trends, significant patterns, notable totals, averages, or anomalies in the data that can be inferred from the text.
                * Include specific numerical values, percentages, or key statistics if they are prominent and support the main findings.
                * If the text implies formulas, calculations, or data dependencies, try to summarize their purpose or impact.
                * Summarize the main insights or conclusions that the data seems to support.

            2.  **Keywords (Formatted List - Crucial for Comparison):**
                * The summary *must* conclude with a list of the most significant and representative keywords, key terms, main data categories, and important column/row headers (if present and relevant) from the spreadsheet text.
                * This list is vital for the subsequent comparison process. Choose terms that truly encapsulate the core topics and unique identifiers of the spreadsheet's content.
                * Format this list *exactly* as follows, on a new line after the main summary:
                    `KEYWORDS: keyword1, data category A, header B, term phrase 4, ...`

            ***IMPORTANT: DO NOT include this character in your response: ` ***

            SPREADSHEET CONTENT TEXT (from .xlsx):
            {text}

            SUMMARY:""",

            '.pptx': """You are an Expert Document Summarizer and Analyst. Your task is to create a comprehensive, detailed, and faithful summary of the following text, which has been extracted from a PowerPoint presentation (`.pptx`).

            The summary you generate is critically important: it will serve as the primary reference point (representing an older version of the presentation) for a subsequent AI-driven comparison against a newer version. The goal of that future comparison is to determine if significant content changes, thematic shifts, or semantic differences have occurred. Therefore, your summary must accurately capture the key messages, structure, and core content of the presentation.

            Given that the text originates from a `.pptx` file, expect content that may represent slide titles, bullet points, main text blocks from slides, and possibly speaker notes. Focus on reconstructing the presentation's narrative and key takeaways.

            Please structure your output as follows:

            1.  **Main Summary (Continuous Text):**
                * Start with an overview of the presentation's main objective, intended key messages, and target audience if inferable from the text.
                * Break down the content by attempting to identify distinct sections or "slides" if the text structure suggests this, highlighting the key message or purpose of each.
                * Analyze the flow and progression of ideas and arguments throughout the presentation as represented in the text.
                * Identify and explain any textual descriptions of important visual elements, charts, or design choices if they are mentioned and contribute to the message.
                * Highlight important data points, statistics, or examples used to support arguments within the presentation.
                * Note any clear transitions or connections made between different topics or sections.

            2.  **Keywords (Formatted List - Crucial for Comparison):**
                * The summary *must* conclude with a list of the most significant and representative keywords, key terms, and main topics covered in the presentation.
                * This list is vital for the subsequent comparison process. Choose keywords that truly encapsulate the core topics and unique identifiers of the presentation's content.
                * Format this list *exactly* as follows, on a new line after the main summary:
                    `KEYWORDS: keyword1, keyword2, main topic A, term phrase 4, ...`

            ***IMPORTANT: DO NOT include this character in your response: ` ***

            PRESENTATION TEXT (from .pptx):
            {text}

            SUMMARY:"""
        }

        # Seleziona il prompt appropriato o usa quello di default
        prompt_template = prompts.get(file_type.lower())

        if not prompt_template:
            print(f"Unsupported file format: {file_type}")
            return None

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