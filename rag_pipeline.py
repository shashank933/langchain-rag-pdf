"""
RAG Pipeline for PDF Question Answering using LangChain + DeepSeek.

This module handles:
- PDF loading and text chunking
- Vector embedding and storage with ChromaDB
- Retrieval and answer generation with DeepSeek LLM
"""

import os
import tempfile
from typing import List, Optional

from dotenv import load_dotenv
from langchain.chains import RetrievalQA
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_deepseek import ChatDeepSeek

load_dotenv()


class RAGPipeline:
    """RAG pipeline that processes PDFs and answers questions using DeepSeek."""

    def __init__(
        self,
        deepseek_api_key: Optional[str] = None,
        model_name: str = "deepseek-chat",
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        k_retrieval: int = 4,
    ):
        """
        Initialize the RAG pipeline.

        Args:
            deepseek_api_key: DeepSeek API key (defaults to DEEPSEEK_API_KEY env var)
            model_name: DeepSeek model to use
            embedding_model: HuggingFace embedding model name
            chunk_size: Size of text chunks for splitting
            chunk_overlap: Overlap between chunks
            k_retrieval: Number of documents to retrieve for context
        """
        self.deepseek_api_key = deepseek_api_key or os.getenv("DEEPSEEK_API_KEY")
        if not self.deepseek_api_key:
            raise ValueError(
                "DeepSeek API key is required. Set DEEPSEEK_API_KEY in .env or pass it directly."
            )

        self.model_name = model_name
        self.embedding_model_name = embedding_model
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.k_retrieval = k_retrieval

        self.embeddings = None
        self.vector_store = None
        self.qa_chain = None
        self._initialize_embeddings()

    def _initialize_embeddings(self):
        """Initialize the HuggingFace embeddings model."""
        self.embeddings = HuggingFaceEmbeddings(
            model_name=self.embedding_model_name,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )

    def _initialize_llm(self):
        """Initialize the DeepSeek LLM."""
        return ChatDeepSeek(
            model=self.model_name,
            api_key=self.deepseek_api_key,
            temperature=0.3,
            max_tokens=2048,
        )

    def load_pdf(self, pdf_path: str) -> int:
        """
        Load a PDF file, split it into chunks, and index it into the vector store.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Number of chunks created
        """
        # Load PDF
        loader = PyPDFLoader(pdf_path)
        documents = loader.load()

        # Split into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=["\n\n", "\n", ".", " ", ""],
        )
        chunks = text_splitter.split_documents(documents)

        # Add metadata
        for i, chunk in enumerate(chunks):
            chunk.metadata["chunk_id"] = i
            chunk.metadata["source"] = os.path.basename(pdf_path)

        # Create vector store
        self.vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory=None,  # In-memory for simplicity
        )

        # Initialize QA chain
        llm = self._initialize_llm()
        retriever = self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": self.k_retrieval},
        )

        self.qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True,
            verbose=False,
        )

        return len(chunks)

    def ask(self, question: str) -> dict:
        """
        Ask a question about the loaded PDF.

        Args:
            question: The question to ask

        Returns:
            Dictionary with 'answer' and 'source_documents' keys
        """
        if not self.qa_chain:
            raise ValueError(
                "No PDF has been loaded yet. Please load a PDF first using load_pdf()."
            )

        result = self.qa_chain.invoke({"query": question})
        return {
            "answer": result["result"],
            "source_documents": result["source_documents"],
        }

    def clear(self):
        """Clear the vector store and QA chain."""
        self.vector_store = None
        self.qa_chain = None
