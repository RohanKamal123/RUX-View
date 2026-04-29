import json
import chromadb
from chromadb.utils import embedding_functions

# Load your JSON file
with open("laws.json", "r", encoding="utf-8") as f:
    laws = json.load(f)

# Initialize Chroma client
client = chromadb.Client()

# Choose an embedding function
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key="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",
    model_name="text-embedding-3-small"
)

# Create a collection and set embedding function here (not in add)
collection = client.create_collection(
    name="land_laws",
    embedding_function=openai_ef
)

# Add documents to collection
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

print("✅ All laws added to ChromaDB!")


# Example user query
query = "জমির নামজারি করতে হলে কী কী কাগজ লাগে?"  # Bengali: "What documents are required for land registration?"

# Search top 3 relevant sections
results = collection.query(
    query_texts=[query],  # your query
    n_results=3           # number of top results
)

# Print results
for i, doc in enumerate(results['documents'][0]):
    metadata = results['metadatas'][0][i]
    print(f"Match {i+1}:")
    print(f"Law: {metadata['law_title']} ({metadata['year']})")
    print(f"Section: {metadata['section_number']} - {metadata['section_title']}")
    print(f"Text: {doc}\n")
