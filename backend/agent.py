# Prima di eseguire questo script, assicurati di installare le librerie necessarie:
# pip install langchain langchain-community pypdf docx2txt openpyxl google-generativeai langchain-google-genai unstructured

import os
import asyncio
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, UnstructuredExcelLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.summarize import load_summarize_chain
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate

# Configurazione Gemini
# IMPORTANTE: Inserisci qui la tua API key di Google Gemini
# Puoi anche impostarla come variabile d'ambiente: GOOGLE_API_KEY
os.environ["GOOGLE_API_KEY"] = "AIzaSyASlsh1jRxd2iZnM3E3FM1TlDZ4yarUUMU"  # Sostituisci con la tua API key

# Configurazione del modello
llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    temperature=0,
    convert_system_message_to_human=True
)

# Prompt per la riassummarizzazione
map_prompt = PromptTemplate(
    template="""Analizza attentamente il seguente testo e crea un riassunto conciso che catturi i punti principali:
    {text}
    
    RIASSUNTO:""",
    input_variables=["text"]
)

combine_prompt = PromptTemplate(
    template="""Sintetizza i seguenti riassunti in un unico riassunto coerente e completo. 
    Assicurati di mantenere tutti i punti chiave e di creare un testo fluido:
    
    {text}
    
    RIASSUNTO FINALE:""",
    input_variables=["text"]
)

# ---------------------------------------------------------------------------

async def get_document_loader(file_path):
    """Restituisce il loader appropriato in base all'estensione del file."""
    _, file_extension = os.path.splitext(file_path)
    if file_extension.lower() == '.pdf':
        return PyPDFLoader(file_path)
    elif file_extension.lower() == '.docx':
        return Docx2txtLoader(file_path)
    elif file_extension.lower() in ['.xlsx', '.xls']:
        # UnstructuredExcelLoader può estrarre testo da diverse celle
        return UnstructuredExcelLoader(file_path, mode="elements")
    else:
        print(f"Formato file non supportato: {file_extension}")
        return None

async def load_document(loader):
    """Carica il documento in modo asincrono."""
    try:
        # Eseguiamo il caricamento in un thread separato per non bloccare l'event loop
        loop = asyncio.get_event_loop()
        documents = await loop.run_in_executor(None, loader.load)
        return documents
    except Exception as e:
        print(f"Errore durante il caricamento del documento: {e}")
        return None

async def summarize_document(file_path: str) -> str:
    """
    Carica, splitta e riassume un documento in modo asincrono.
    """
    if not os.path.exists(file_path):
        return f"Errore: Il file {file_path} non esiste."

    print(f"Caricamento del documento: {file_path}...")
    loader = await get_document_loader(file_path)
    if not loader:
        return "Impossibile caricare il documento."

    documents = await load_document(loader)
    if not documents:
        return "Nessun contenuto estratto dal documento."

    print(f"Documento caricato. Numero di pagine/sezioni estratte: {len(documents)}")
    # print("Contenuto grezzo della prima pagina/sezione (primi 200 caratteri):")
    # print(documents[0].page_content[:200])
    # print("-" * 20)

    print("Divisione del testo in chunks...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=4000, chunk_overlap=200)
    split_texts = text_splitter.split_documents(documents)
    print(f"Numero di chunks creati: {len(split_texts)}")

    if not split_texts:
        return "Nessun testo da riassumere dopo la divisione."

    chain_type_to_use = "map_reduce"
    if len(split_texts) == 1:
        chain_type_to_use = "stuff"

    print(f"Avvio della riassummarizzazione con la chain di tipo '{chain_type_to_use}'...")
    try:
        # Configurazione della chain con prompt appropriati
        if chain_type_to_use == "stuff":
            summary_chain = load_summarize_chain(
                llm,
                chain_type="stuff",
                verbose=True
            )
        else:
            summary_chain = load_summarize_chain(
                llm,
                chain_type="map_reduce",
                map_prompt=PromptTemplate(
                    template="""Analizza attentamente il seguente testo e crea un riassunto conciso che catturi i punti principali:
                    {text}
                    
                    RIASSUNTO:""",
                    input_variables=["text"]
                ),
                combine_prompt=PromptTemplate(
                    template="""Sintetizza i seguenti riassunti in un unico riassunto coerente e completo. 
                    Assicurati di mantenere tutti i punti chiave e di creare un testo fluido:
                    
                    {text}
                    
                    RIASSUNTO FINALE:""",
                    input_variables=["text"]
                ),
                verbose=True
            )

        # Eseguiamo la chain in modo asincrono
        loop = asyncio.get_event_loop()
        summary_output = await loop.run_in_executor(
            None,
            lambda: summary_chain.invoke({"input_documents": split_texts})
        )
        final_summary = summary_output.get("output_text", "Nessun riassunto generato.")

    except Exception as e:
        return f"Errore durante la riassummarizzazione: {e}"

    return final_summary

async def main():
    # --- Crea file di esempio (opzionale, puoi usare i tuoi) ---
    # File DOCX
    try:
        from docx import Document

        doc = Document()
        doc.add_paragraph("Questo è un documento di prova per il riassunto.")
        doc.add_paragraph("LangChain è uno strumento potente per lavorare con LLM.")
        doc.add_paragraph(
            "Questo file .docx sarà processato per estrarre il suo contenuto testuale e generare un riassunto conciso. Speriamo che l'esempio funzioni correttamente e dimostri le capacità del sistema nel gestire diversi formati di file, inclusi i documenti Word.")
        doc.save("esempio.docx")
        print("File 'esempio.docx' creato.")
    except ImportError:
        print(
            "Libreria 'python-docx' non trovata. Impossibile creare 'esempio.docx'. Scaricala con 'pip install python-docx'")
    except Exception as e:
        print(f"Errore nella creazione di esempio.docx: {e}")

    # File PDF (Creazione più complessa, usa un PDF esistente o creane uno semplice)
    # Per semplicità, questo script non crea un PDF. Assicurati di avere un 'esempio.pdf'.
    # Puoi creare un PDF da esempio.docx usando Word o uno strumento online.
    # Qui assumiamo che tu ne abbia uno chiamato 'esempio.pdf'
    # Se non hai 'esempio.pdf', il test per PDF fallirà.
    # Esempio di come potresti creare un PDF semplice (richiede reportlab)
    try:
        from reportlab.pdfgen import canvas

        c = canvas.Canvas("esempio.pdf")
        c.drawString(72, 800, "Questo è un file PDF di esempio per il test di riassummarizzazione.")
        c.drawString(72, 780, "Contiene del testo che LangChain dovrebbe essere in grado di processare.")
        c.drawString(72, 760, "L'obiettivo è ottenere un riassunto testuale di questo contenuto.")
        c.save()
        print("File 'esempio.pdf' creato.")
    except ImportError:
        print(
            "Libreria 'reportlab' non trovata. Impossibile creare 'esempio.pdf'. Scaricala con 'pip install reportlab'")
    except Exception as e:
        print(f"Errore nella creazione di esempio.pdf: {e}")

    # File XLSX
    try:
        import openpyxl

        workbook = openpyxl.Workbook()
        sheet = workbook.active
        sheet["A1"] = "Dati di esempio per XLSX."
        sheet["B2"] = "LangChain può leggere anche file Excel."
        sheet[
            "C3"] = "Questa è la cella C3 e contiene informazioni utili per il riassunto del foglio di calcolo. Lo scopo è testare l'estrazione da diverse celle."
        workbook.save("esempio.xlsx")
        print("File 'esempio.xlsx' creato.")
    except ImportError:
        print(
            "Libreria 'openpyxl' non trovata. Impossibile creare 'esempio.xlsx'. Scaricala con 'pip install openpyxl'")
    except Exception as e:
        print(f"Errore nella creazione di esempio.xlsx: {e}")

    print("-" * 30)

    # --- Esegui la riassummarizzazione sui file di esempio ---
    files_to_summarize = []
    if os.path.exists("esempio.docx"):
        files_to_summarize.append("esempio.docx")
    else:
        print("Skipping esempio.docx: File non trovato.")

    if os.path.exists("esempio.pdf"):
        files_to_summarize.append("esempio.pdf")
    else:
        print("Skipping esempio.pdf: File non trovato.")

    if os.path.exists("esempio.xlsx"):
        files_to_summarize.append("esempio.xlsx")
    else:
        print("Skipping esempio.xlsx: File non trovato.")

    if not files_to_summarize:
        print(
            "\nNessun file di esempio trovato o creato. Assicurati di avere i file .docx, .pdf, .xlsx nella stessa directory o crea i file di esempio.")
    else:
        # Esegui la riassummarizzazione in parallelo per tutti i file
        tasks = [summarize_document(file) for file in files_to_summarize]
        summaries = await asyncio.gather(*tasks)
        
        for file, summary in zip(files_to_summarize, summaries):
            print(f"\n--- Riassunto per: {file} ---")
            print("\nRIASSUNTO FINALE:")
            print(summary)
            print("-" * 30)

if __name__ == "__main__":
    asyncio.run(main())

    # Pulizia (opzionale)
    # try:
    #     if os.path.exists("esempio.docx"): os.remove("esempio.docx")
    #     if os.path.exists("esempio.pdf"): os.remove("esempio.pdf")
    #     if os.path.exists("esempio.xlsx"): os.remove("esempio.xlsx")
    #     print("\nFile di esempio rimossi.")
    # except Exception as e:
    #     print(f"Errore durante la rimozione dei file di esempio: {e}")