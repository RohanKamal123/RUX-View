import openai
import chromadb
import os
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
import json
from data.ict_data import ict_data, search_data

# Load environment variables
load_dotenv()

# Set OpenAI API key directly (for quick testing)
api_key = "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"

# Initialize OpenAI client
from openai import OpenAI
client = OpenAI(api_key=api_key)

class ICTRagEngine:
    def __init__(self):
        # Initialize ChromaDB
        self.client = chromadb.Client()
        self.collection = None
        
        # Initialize sentence transformer for embeddings
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Initialize the knowledge base
        self.setup_knowledge_base()
    
    def setup_knowledge_base(self):
        """Setup ChromaDB with ICT data"""
        try:
            # Delete existing collection if it exists
            try:
                self.client.delete_collection("ict_knowledge")
            except:
                pass
            
            # Create new collection
            self.collection = self.client.create_collection(
                name="ict_knowledge",
                metadata={"description": "HSC ICT Knowledge Base"}
            )
            
            # Prepare data for ChromaDB
            documents = []
            metadatas = []
            ids = []
            
            for item in ict_data:
                # Combine question and answer for better search
                doc_text = f"প্রশ্ন: {item['question']}\nউত্তর: {item['answer']}"
                documents.append(doc_text)
                
                metadatas.append({
                    "topic": item["topic"],
                    "type": item["type"],
                    "difficulty": item["difficulty"],
                    "tags": json.dumps(item["tags"])
                })
                
                ids.append(str(item["id"]))
            
            # Add to ChromaDB
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            
            print(f"✅ Knowledge base setup complete with {len(ict_data)} entries!")
            
        except Exception as e:
            print(f"❌ Error setting up knowledge base: {e}")
    
    def search_knowledge(self, query, n_results=3):
        """Search for relevant knowledge"""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results
            )
            return results
        except Exception as e:
            print(f"❌ Search error: {e}")
            return None
    
    def generate_answer(self, question, context_docs=None):
        """Generate answer using OpenAI with context"""
        try:
            # If no context provided, search for it
            if not context_docs:
                search_results = self.search_knowledge(question)
                if search_results and search_results['documents']:
                    context_docs = search_results['documents'][0]
                else:
                    context_docs = []
            
            # Prepare context
            context = "\n\n".join(context_docs) if context_docs else "No specific context found."
            
            # ICT-specific prompt
            prompt = f"""তুমি একজন অভিজ্ঞ HSC ICT শিক্ষক। নিচের প্রসঙ্গ ব্যবহার করে প্রশ্নের উত্তর দাও।

নিয়মাবলী:
1. সহজ বাংলায় ব্যাখ্যা করো
2. উদাহরণ দিয়ে বুঝাও
3. HSC পরীক্ষার প্যাটার্ন অনুসরণ করো
4. যদি programming সম্পর্কে হয় তাহলে code example দাও

প্রসঙ্গ:
{context}

প্রশ্ন: {question}

উত্তর:"""

            # Call OpenAI API
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert HSC ICT teacher who explains concepts in simple Bengali."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            return f"দুঃখিত, উত্তর তৈরি করতে সমস্যা হয়েছে। Error: {str(e)}"
    
    def get_topic_suggestions(self):
        """Get available topics"""
        topics = list(set([item["topic"] for item in ict_data]))
        return sorted(topics)
    
    def answer_question(self, question):
        """Main function to answer any ICT question"""
        try:
            # First try exact search in our data
            search_results = search_data(question)
            
            if search_results:
                # Use our curated data
                best_match = search_results[0]
                return best_match["answer"]
            else:
                # Use RAG with AI generation
                return self.generate_answer(question)
                
        except Exception as e:
            return f"দুঃখিত, কিছু সমস্যা হয়েছে। আবার চেষ্টা করুন।"

# Initialize the engine (will be used in Streamlit app)
rag_engine = None

def get_rag_engine():
    """Get or create RAG engine instance"""
    global rag_engine
    if rag_engine is None:
        rag_engine = ICTRagEngine()
    return rag_engine