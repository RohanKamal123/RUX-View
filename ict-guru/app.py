import streamlit as st
import time
from rag_engine import get_rag_engine
from data.ict_data import ict_data

# Configure page
st.set_page_config(
    page_title="ICT Guru - HSC ICT AI Tutor",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better UI
st.markdown("""
<style>
    .main-header {
        text-align: center;
        color: #1f77b4;
        font-size: 3rem;
        font-weight: bold;
        margin-bottom: 1rem;
    }
    .sub-header {
        text-align: center;
        color: #666;
        font-size: 1.2rem;
        margin-bottom: 2rem;
    }
    .question-box {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
        margin: 1rem 0;
    }
    .answer-box {
        background-color: #e8f4fd;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #28a745;
        margin: 1rem 0;
    }
    .stats-box {
        background-color: #fff3cd;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'rag_engine' not in st.session_state:
    st.session_state.rag_engine = None
if 'question_history' not in st.session_state:
    st.session_state.question_history = []

def initialize_engine():
    """Initialize the RAG engine"""
    if st.session_state.rag_engine is None:
        with st.spinner("🔄 ICT Guru শুরু করা হচ্ছে..."):
            try:
                st.session_state.rag_engine = get_rag_engine()
                st.success("✅ ICT Guru প্রস্তুত!")
                return True
            except Exception as e:
                st.error(f"❌ Error initializing ICT Guru: {e}")
                return False
    return True

def main():
    # Header
    st.markdown('<h1 class="main-header">🎓 ICT Guru</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">HSC ICT এর জন্য আপনার AI শিক্ষক</p>', unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.header("📊 তথ্য")
        
        # Stats
        st.markdown(f"""
        <div class="stats-box">
            <h3>📚 Knowledge Base</h3>
            <p><strong>{len(ict_data)}</strong> টি প্রশ্ন ও উত্তর</p>
            <p><strong>HSC ICT</strong> সিলেবাস অনুযায়ী</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Available Topics  
        if 'rag_engine' in st.session_state and st.session_state.rag_engine:
            topics = st.session_state.rag_engine.get_topic_suggestions()
            st.subheader("📝 Available Topics")
            for topic in topics:
                st.write(f"• {topic}")
        
        # Question History
        if st.session_state.question_history:
            st.subheader("📜 Recent Questions")
            for q in st.session_state.question_history[-5:]:
                st.write(f"• {q[:50]}...")
    
    # Main content
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Initialize engine
        if not initialize_engine():
            st.stop()
        
        # Question input
        st.subheader("❓ আপনার প্রশ্ন করুন")
        
        question = st.text_area(
            "ICT সম্পর্কে যেকোনো প্রশ্ন করুন (বাংলা বা ইংরেজিতে):",
            height=100,
            placeholder="উদাহরণ: C ভাষায় variable কি? বা What is DBMS?"
        )
        
        # Example questions
        st.write("**Quick Examples:**")
        example_questions = [
            "C ভাষায় variable কি?",
            "DBMS কি?", 
            "OSI Model এর layer গুলো কি?",
            "HTML tag কি?",
            "Database normalization কি?"
        ]
        
        cols = st.columns(len(example_questions))
        for i, eq in enumerate(example_questions):
            with cols[i]:
                if st.button(f"{eq[:15]}...", key=f"example_{i}"):
                    question = eq
        
        # Submit button
        if st.button("🔍 উত্তর খুঁজুন", type="primary", use_container_width=True):
            if question.strip():
                # Add to history
                st.session_state.question_history.append(question)
                
                # Display question
                st.markdown(f'''
                <div class="question-box">
                    <h4>📝 প্রশ্ন:</h4>
                    <p>{question}</p>
                </div>
                ''', unsafe_allow_html=True)
                
                # Get answer
                with st.spinner("🤔 চিন্তা করছি..."):
                    try:
                        answer = st.session_state.rag_engine.answer_question(question)
                        
                        # Display answer
                        st.markdown(f'''
                        <div class="answer-box">
                            <h4>✅ উত্তর:</h4>
                            <p>{answer}</p>
                        </div>
                        ''', unsafe_allow_html=True)
                        
                    except Exception as e:
                        st.error(f"দুঃখিত, উত্তর দিতে সমস্যা হয়েছে: {e}")
            else:
                st.warning("অনুগ্রহ করে একটি প্রশ্ন লিখুন!")
    
    with col2:
        # Tips and help
  
        
        st.subheader("📚 Covered Topics")
        st.write("""
        - Programming (C Language)
        - Database (DBMS, SQL)
        - Networkingt
        - Web Development (HTML, CSS)
        - Number Systems
        - Computer Fundamentals
        """)
        
        st.subheader("🚀 Features")
        st.write("""
        - ✅ Bengali Language Support
        - ✅ HSC Pattern Answers
        - ✅ Code Examples
        - ✅ Instant Responses
        - ✅ Topic-wise Organization
        """)
    
    # Footer
    st.markdown("---")
    st.markdown(
        "<p style='text-align: center; color: #666;'>Made with ❤️ for HSC ICT Students | Powered by AI</p>", 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()