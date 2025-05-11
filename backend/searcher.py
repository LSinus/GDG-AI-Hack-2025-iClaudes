from sentence_transformers import SentenceTransformer
import os
import asyncio
import google.generativeai as genai
from app import load_embedding_model
from app import get_redis_connection
from app import VECTOR_SET_NAME

# Configurazione Gemini
GOOGLE_API_KEY = "AIzaSyASlsh1jRxd2iZnM3E3FM1TlDZ4yarUUMU"
genai.configure(api_key=GOOGLE_API_KEY)

# Configurazione del modello
model = genai.GenerativeModel('gemini-2.0-flash')

async def analyze_search_query(query: str) -> str:
    """Analizza e chiarifica una query di ricerca usando Gemini."""
    try:
        prompt = """You are an AI assistant specializing in interpreting user information needs and hypothesizing document content.
                    Analyze the following search query provided by a user. Your task is NOT to describe what the user is looking for, nor to paraphrase their request.

                    Instead, you must generate text that represents a concise and informative summary of the *key content points of the document* the user is presumably searching for. Imagine an LLM has read that specific document and extracted its key information and potential implications.

                    Your output must:
                    1.  **Identify the main topic and purpose of the target document.** For example, if the query mentions 'specification of a university hardware project,' the target document might be a technical report or a design document.
                    2.  **Extract and detail the technical components, methodologies, or specific concepts mentioned in the query.** For instance, if the query cites a 'differential filter,' the summary should briefly elaborate on its function within the project's context.
                    3.  **Make logical and plausible inferences about aspects of the project/document that the user may not have explicitly stated but are typically associated with the given context.** These inferences should enrich the description of the document's content. For example:
                        * If a 'university project' is mentioned, you can infer that the document might contain sections such as 'theoretical background,' 'objectives,' 'requirements analysis,' 'design choices,' 'development phases,' 'schematics/block diagrams,' 'test results/simulations,' and 'conclusions/future work.'
                        * If 'hardware with a differential filter' is mentioned, you can infer that the purpose might involve acquiring weak signals in noisy environments, precision measurement, or interfacing with specific sensors.
                    4.  **Produce a flowing and coherent text that directly describes the *hypothetical content* of the document.** Do not use phrases like 'The user is looking for...' or 'The file might contain...'. Begin directly by describing the document.
                    5.  **You MUST write in a clean text format, without formatting it in rows, stars, number lists, etc.**

                    Here is the user's query:
                    "{query}"

                    Considering the provided query, now generate the hypothetical summary of the salient points of the *content of the document* the user is searching for."""

        prompt = prompt.format(query=query)
        
        response = await asyncio.to_thread(
            model.generate_content,
            prompt
        )
        
        return response.text
    except Exception as e:
        print(f"Error during query analysis: {e}")
        return None

async def main():
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python searcher.py \"<search query>\"")
        return

    query = sys.argv[1]
    analysis = await analyze_search_query(query)
    
    if analysis:
        print("\nQUERY ANALYSIS:")
        print(analysis)
    print("-" * 30)

    model = load_embedding_model()
    redis_client = get_redis_connection()

    if not self.redis_client:
            print("[CRITICAL] Failed to connect to Redis. Embedding storage will not work.")
    if not self.embedding_model:
        print("[CRITICAL] Failed to load embedding model. Embedding generation will not work.")
    

    embedding = model.encode(file_content).tolist()

    res = redis_client.vset().vsim(VECTOR_SET_NAME, embedding)

    print(res)



if __name__ == "__main__":
    asyncio.run(main())

