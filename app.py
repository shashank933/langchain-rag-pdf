"""
Streamlit UI for LangChain RAG with DeepSeek - PDF Question Answering.

Upload a PDF and ask questions about its content using DeepSeek LLM.
"""

import os
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from rag_pipeline import RAGPipeline, GuardrailViolation

load_dotenv()

# Page configuration
st.set_page_config(
    page_title="SmartChat — Talk to Your PDFs",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown(
    """
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .stChatMessage {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1rem;
        color: #000000 !important;
    }
    .stChatMessage p {
        color: #000000 !important;
    }
    .stChatMessage div {
        color: #000000 !important;
    }
    .stChatMessage span {
        color: #000000 !important;
    }
    .stChatMessage li {
        color: #000000 !important;
    }
    .stChatMessage ol {
        color: #000000 !important;
    }
    .stChatMessage ul {
        color: #000000 !important;
    }
    .source-box {
        background-color: #f0f2f6;
        border-left: 3px solid #4CAF50;
        padding: 0.75rem;
        border-radius: 4px;
        margin: 0.5rem 0;
        font-size: 0.85rem;
    }
    .status-ok {
        color: #4CAF50;
        font-weight: 600;
    }
    .status-waiting {
        color: #FF9800;
        font-weight: 600;
    }
</style>
""",
    unsafe_allow_html=True,
)


def initialize_session_state():
    """Initialize Streamlit session state variables."""
    if "rag_pipeline" not in st.session_state:
        st.session_state.pdf_loaded = False
    if "chunk_count" not in st.session_state:
        st.session_state.chunk_count = 0
    if "pdf_name" not in st.session_state:
        st.session_state.pdf_name = ""
    if "messages" not in st.session_state:
        st.session_state.messages = []


def main():
    initialize_session_state()

    # Sidebar
    with st.sidebar:
        st.markdown("## 💬 SmartChat")
      

        st.markdown("### 📤 Upload PDF")
        uploaded_file = st.file_uploader(
            "Choose a PDF file",
            type=["pdf"],
            help="Upload a PDF document to ask questions about",
        )

        if uploaded_file is not None:
            if st.button("🔄 Process PDF", type="primary", use_container_width=True):
                with st.spinner("Processing PDF... This may take a moment."):
                    try:
                        # Save uploaded file to temp location
                        with tempfile.NamedTemporaryFile(
                            delete=False, suffix=".pdf"
                        ) as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_path = tmp_file.name

                        # Initialize pipeline
                        pipeline = RAGPipeline(deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"))

                        # Load and index PDF
                        chunk_count = pipeline.load_pdf(tmp_path)

                        # Clean up temp file
                        os.unlink(tmp_path)

                        # Store in session state
                        st.session_state.rag_pipeline = pipeline
                        st.session_state.pdf_loaded = True
                        st.session_state.chunk_count = chunk_count
                        st.session_state.pdf_name = uploaded_file.name
                        st.session_state.messages = []  # Reset chat

                        st.success(
                            f"✅ Processed '{uploaded_file.name}' into {chunk_count} chunks!"
                        )
                    except Exception as e:
                        st.error(f"❌ Error processing PDF: {str(e)}")

        # Status display
        st.markdown("---")
        st.markdown("### 📊 Status")

        if st.session_state.pdf_loaded:
            st.markdown(
                f'<p class="status-ok">✅ PDF Loaded: {st.session_state.pdf_name}</p>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f"**Chunks:** {st.session_state.chunk_count}",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<p class="status-waiting">⏳ Waiting for PDF upload...</p>',
                unsafe_allow_html=True,
            )

        # Clear button
        if st.session_state.pdf_loaded:
            if st.button("🗑️ Clear & Reset", use_container_width=True):
                st.session_state.rag_pipeline = None
                st.session_state.pdf_loaded = False
                st.session_state.messages = []
                st.session_state.chunk_count = 0
                st.session_state.pdf_name = ""
                st.rerun()

        st.markdown("---")
        st.markdown(
            """
        **How it works:**
        1. Upload a PDF
        2. PDF is split into chunks
        3. Chunks are embedded & indexed
        4. Ask questions in natural language
        5. DeepSeek answers with citations
        """
        )

    # Main chat area
    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown(
            '<h1 class="main-header">💬 SmartChat</h1>',
            unsafe_allow_html=True,
        )
    with col2:
        if st.session_state.pdf_loaded:
            st.markdown(
                f'<div style="text-align: right; padding-top: 1.5rem;">'
                f'<span class="status-ok">✅ {st.session_state.pdf_name}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )

    st.markdown(
        '<p class="sub-header">Upload a PDF and ask questions — powered by LangChain + DeepSeek RAG</p>',
        unsafe_allow_html=True,
    )

    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "sources" in message and message["sources"]:
                with st.expander("📚 View Sources", expanded=False):
                    for i, source in enumerate(message["sources"], 1):
                        st.markdown(
                            f'<div class="source-box">'
                            f"<strong>Source {i}</strong> (Page {source.metadata.get('page', 'N/A')})<br>"
                            f"{source.page_content[:300]}..."
                            f"</div>",
                            unsafe_allow_html=True,
                        )

    # Chat input
    if st.session_state.pdf_loaded:
        prompt = st.chat_input("Ask a question about your PDF...")
        if prompt:
            # Add user message
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            # Generate response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    try:
                        result = st.session_state.rag_pipeline.ask(prompt)
                        answer = result["answer"]
                        sources = result["source_documents"]

                        st.markdown(answer)

                        if sources:
                            with st.expander("📚 View Sources", expanded=False):
                                for i, source in enumerate(sources, 1):
                                    st.markdown(
                                        f'<div class="source-box">'
                                        f"<strong>Source {i}</strong> "
                                        f"(Page {source.metadata.get('page', 'N/A')})<br>"
                                        f"{source.page_content[:300]}..."
                                        f"</div>",
                                        unsafe_allow_html=True,
                                    )

                        # Store in session
                        st.session_state.messages.append(
                            {
                                "role": "assistant",
                                "content": answer,
                                "sources": sources,
                            }
                        )
                    except GuardrailViolation as e:
                        refusal_msg = str(e)
                        st.warning(refusal_msg)
                        st.session_state.messages.append(
                            {
                                "role": "assistant",
                                "content": refusal_msg,
                                "sources": [],
                            }
                        )
                    except Exception as e:
                        error_msg = f"❌ Error: {str(e)}"
                        st.error(error_msg)
                        st.session_state.messages.append(
                            {"role": "assistant", "content": error_msg}
                        )
    else:
        st.info("👈 Please upload a PDF file using the sidebar to get started.")


if __name__ == "__main__":
    main()
