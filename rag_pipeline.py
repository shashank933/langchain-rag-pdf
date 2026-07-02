"""
RAG Pipeline for PDF Question Answering using LangChain + DeepSeek.

This module handles:
- PDF loading and text chunking
- Vector embedding and storage with ChromaDB
- Retrieval and answer generation with DeepSeek LLM
- Input guardrails to reject unethical or off-topic queries
"""

import os
import re
import tempfile
from typing import List, Optional

from dotenv import load_dotenv
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_deepseek import ChatDeepSeek

load_dotenv()

GUARDRAIL_PROMPT_TEMPLATE = """You are a helpful assistant that ONLY answers questions related to the content of uploaded PDF documents.

RULES:
1. Answer questions based strictly on the provided document context below.
2. If the answer is not found in the context, say "I cannot find this information in the uploaded PDF."
3. If the question is unethical, harmful, illegal, offensive, promotes violence/hate/self-harm, or requests inappropriate content, REFUSE to answer. Reply: "I cannot answer that question. Please ask a question related to the uploaded PDF document."
4. If the question is completely unrelated to document content (e.g., general chat, coding help, personal advice, current events), politely redirect: "I can only answer questions related to the uploaded PDF document. Please ask a question about the PDF content."
5. Do not role-play, generate harmful code, provide medical/legal advice, or engage in discussions about sensitive topics unless they are explicitly part of the document content.
6. Keep answers concise, factual, and grounded in the document context.

Context from the PDF document:
{context}

Question: {question}
Helpful Answer:"""

GUARDRAIL_REFUSAL_MESSAGE = (
    "I cannot answer that question. Please ask a question related to the uploaded PDF document."
)

UNETHICAL_PATTERNS = [
    r"\b(hack|hacking|crack|exploit|malware|ransomware|phish)\b",
    r"\b(how to (make|build|create|manufacture) (a )?(bomb|weapon|drug|meth|explosive))\b",
    r"\b(suicide|kill (yourself|myself|people)|self.?harm|self.?injury)\b",
    r"\b(child (porn|abuse|exploitation)|csam|pedophil)\b",
    r"\b(racist|sexist|homophobic|transphobic|xenophobic|hate speech)\b",
    r"\b(how to (steal|rob|defraud|launder|commit fraud|scam))\b",
    r"\b(torture|genocide|terroris|mass (shooting|murder|killing))\b",
    r"\b(sexual (assault|violence|harassment)|rape)\b",
    r"\b(incit(e|ing) (violence|hatred|discrimination))\b",
    r"\b(social (security|insurance) number|credit card (number|details)|ssn|dob|date of birth)",
    r"\b(ignore (all |previous |your )?(instructions|prompts|rules|guidelines))\b",
    r"\b((pretend|act|roleplay|imagine) (you are|as if|as a))\b",
    r"\b(forget (all |previous |your )?(instructions|prompts|rules|guidelines))\b",
    r"\b(you are now (dan|jailbreak|unfiltered|unrestricted))\b",
    r"\b(disregard (all |previous )?(instructions|prompts|rules|guidelines))\b",
]


class GuardrailViolation(Exception):
    """Raised when a question violates content guardrails."""
    pass


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

        self._compile_patterns()
        self.embeddings = None
        self.vector_store = None
        self.qa_chain = None
        self._initialize_embeddings()

    def _compile_patterns(self):
        """Pre-compile guardrail regex patterns for performance."""
        self._unethical_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in UNETHICAL_PATTERNS
        ]

    def _check_guardrails(self, question: str) -> None:
        """
        Check if the question violates content guardrails.

        Args:
            question: The user's question

        Raises:
            GuardrailViolation: If the question matches unethical/off-topic patterns
        """
        question_lower = question.lower().strip()

        for pattern in self._unethical_patterns:
            if pattern.search(question_lower):
                raise GuardrailViolation(GUARDRAIL_REFUSAL_MESSAGE)

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

        # Initialize QA chain with guardrail prompt
        llm = self._initialize_llm()
        retriever = self.vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": self.k_retrieval},
        )

        guardrail_prompt = PromptTemplate(
            template=GUARDRAIL_PROMPT_TEMPLATE,
            input_variables=["context", "question"],
        )

        self.qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True,
            chain_type_kwargs={"prompt": guardrail_prompt},
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

        Raises:
            ValueError: If no PDF is loaded
            GuardrailViolation: If the question violates content guardrails
        """
        if not self.qa_chain:
            raise ValueError(
                "No PDF has been loaded yet. Please load a PDF first using load_pdf()."
            )

        self._check_guardrails(question)

        result = self.qa_chain.invoke({"query": question})
        return {
            "answer": result["result"],
            "source_documents": result["source_documents"],
        }

    def clear(self):
        """Clear the vector store and QA chain."""
        self.vector_store = None
        self.qa_chain = None
