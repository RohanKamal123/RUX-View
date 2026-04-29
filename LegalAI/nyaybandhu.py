import json
import chromadb
from chromadb.utils import embedding_functions
import openai

# Set OpenAI API key (replace with your actual key if needed)
openai.api_key = "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"

def load_laws(file_path):
    """
    Load laws from a JSON file.
    Args:
        file_path (str): Path to the JSON file containing laws.
    Returns:
        list: List of law dictionaries.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: File {file_path} not found.")
        return []
    except json.JSONDecodeError:
        print(f"Error: Invalid JSON in {file_path}.")
        return []
    except Exception as e:
        print(f"Error loading laws: {e}")
        return []

def retrieve_laws(query):
    """
    Retrieve top 3 relevant law sections from ChromaDB based on the query.
    Args:
        query (str): User's query string.
    Returns:
        tuple: (retrieved_texts, metadatas) where retrieved_texts is list of text strings,
               and metadatas is list of metadata dictionaries.
    """
    try:
        results = collection.query(query_texts=[query], n_results=3)
        if results and 'documents' in results and results['documents']:
            return results['documents'][0], results['metadatas'][0]
        else:
            return [], []
    except Exception as e:
        print(f"Error retrieving laws: {e}")
        return [], []

def generate_answer(query, retrieved_texts, metadatas):
    """
    Generate a Bengali answer using OpenAI based on retrieved texts and metadatas.
    Args:
        query (str): User's query.
        retrieved_texts (list): List of retrieved text strings.
        metadatas (list): List of metadata dictionaries.
    Returns:
        str: Generated Bengali answer with citations.
    """
    if not retrieved_texts:
        return "দুঃখিত, প্রাসঙ্গিক তথ্য পাওয়া যায়নি।"  # Bengali: "Sorry, no relevant information found."

    # Combine retrieved texts into context
    context = "\n\n".join(retrieved_texts)

    # Create prompt for OpenAI
    prompt = f"""
আপনি একটি আইন সহকারী চ্যাটবট। ব্যবহারকারীর প্রশ্নের উত্তর শুধুমাত্র নিচের তথ্য ব্যবহার করে দিন এবং বাংলায় সহজভাবে ব্যাখ্যা করুন। সূত্র উল্লেখ করুন।

প্রশ্ন: {query}

প্রাসঙ্গিক তথ্য:
{context}

উত্তর (বাংলায়) + সূত্র:
"""

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful legal assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating answer: {e}")
        return "উত্তর তৈরি করতে সমস্যা হয়েছে।"  # Bengali: "Problem generating answer."

# Initialize ChromaDB client with persistent storage
client = chromadb.PersistentClient(path="./chroma_db")

# Set up OpenAI embedding function
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=openai.api_key,
    model_name="text-embedding-3-small"
)

# Get or create collection with embedding function attached
collection = client.get_or_create_collection(
    name="land_laws",
    embedding_function=openai_ef
)

# Load laws and add to collection if not already present
if collection.count() == 0:
    print("Loading laws into ChromaDB...")
    laws = load_laws("laws.json")
    if laws:
        for law in laws:
            collection.add(
                documents=[law["text"]],
                metadatas=[{
                    "law_title": law["law_title"],
                    "section_number": law["section_number"],
                    "section_title": law["section_title"],
                    "year": law["year"],
                    "source": law["source"]
                }],
                ids=[f"{law['law_title']}_{law['section_number']}"]
            )
        print("All laws added to ChromaDB successfully!")
    else:
        print("No laws loaded. Exiting.")
        exit(1)
else:
    print("Laws already loaded in ChromaDB.")

# Main execution flow
if __name__ == "__main__":
    # Accept user query from console
    query = input("Enter your question: ")

    # Retrieve relevant laws
    retrieved_texts, metadatas = retrieve_laws(query)

    # Generate answer
    answer = generate_answer(query, retrieved_texts, metadatas)

    # Print the answer
    print("\nNyaybandhu উত্তর:\n", answer)