"""
RAG Database Builder Script

This script processes PDF files from a specified folder, extracts text content,
performs chunking, creates embeddings, and stores them in a vector database.
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import logging

# For PDF processinga
import pypdf

# For embedding and vector database
from langchain_chroma import Chroma # Updated import
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document
import dotenv
import google.generativeai as genai

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_environment():
    """Load environment variables from .env file"""
    dotenv.load_dotenv()
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        logger.error("GOOGLE_API_KEY not found in environment variables")
        sys.exit(1)
    genai.configure(api_key=api_key)
    return api_key

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text content from a PDF file"""
    logger.info(f"Extracting text from {pdf_path}")
    
    try:
        with open(pdf_path, 'rb') as file:
            pdf_reader = pypdf.PdfReader(file)
            text = ""
            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                text += page.extract_text() + "\n"
            return text
    except Exception as e:
        logger.error(f"Error extracting text from {pdf_path}: {e}")
        return ""

def chunk_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
    """Split text into overlapping chunks of specified size"""
    logger.info(f"Chunking text with chunk size {chunk_size} and overlap {chunk_overlap}")
    
    if not text:
        return []
        
    chunks = []
    for i in range(0, len(text), chunk_size - chunk_overlap):
        chunk = text[i:i + chunk_size]
        if chunk:  # Ensure we don't add empty chunks
            chunks.append(chunk)
    
    logger.info(f"Created {len(chunks)} chunks")
    return chunks

def create_metadata(source_file: str, chunk_index: int) -> Dict[str, Any]:
    """Create metadata for a text chunk"""
    return {
        "source": source_file,
        "chunk_index": chunk_index,
    }

def process_pdf_folder(folder_path: str, db_path: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> None:
    """Process all PDFs in a folder and create a vector database"""
    logger.info(f"Processing PDFs from folder: {folder_path}")
    
    api_key = load_environment()
    
    # Initialize the embedding model
    embedding_function = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001",
        google_api_key=api_key,
    )
    
    # Initialize or load the vector database
    if os.path.exists(db_path):
        logger.info(f"Loading existing vector database from {db_path}")
        vector_db = Chroma(persist_directory=db_path, embedding_function=embedding_function)
    else:
        logger.info(f"Creating new vector database at {db_path}")
        os.makedirs(db_path, exist_ok=True)
        vector_db = Chroma(persist_directory=db_path, embedding_function=embedding_function)
    
    # Process each PDF in the folder
    pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        logger.warning(f"No PDF files found in {folder_path}")
        return
    
    logger.info(f"Found {len(pdf_files)} PDF files to process")
    
    for pdf_file in pdf_files:
        pdf_path = os.path.join(folder_path, pdf_file)
        
        # Extract text from PDF
        text = extract_text_from_pdf(pdf_path)
        
        if not text:
            logger.warning(f"No text extracted from {pdf_file}, skipping")
            continue
        
        # Chunk the text
        chunks = chunk_text(text, chunk_size, chunk_overlap)
        
        # Create proper LangChain Document objects with metadata
        documents = []
        for i, chunk in enumerate(chunks):
            metadata = create_metadata(pdf_file, i)
            # Create a proper LangChain Document object
            doc = Document(page_content=chunk, metadata=metadata)
            documents.append(doc)
        
        # Add to vector database
        logger.info(f"Adding {len(documents)} documents to vector database from {pdf_file}")
        try:
            vector_db.add_documents(documents)
        except Exception as e:
            logger.error(f"Error adding documents to database: {e}")
    
    # Persist the database
    logger.info("Persisting vector database")
    try:
        vector_db.persist()
    except Exception as e:
        logger.warning(f"Persist warning (can be ignored for newer Chroma versions): {e}")
    logger.info(f"Vector database created successfully at {db_path}")

def main():
    parser = argparse.ArgumentParser(description="Build a RAG vector database from PDF files")
    parser.add_argument(
        "--pdf_folder", 
        type=str, 
        default="C:\\Users\\tosah\\Desktop\\baseApp\\knowledege_data_pdf",
        help="Folder containing PDF files"
    )
    parser.add_argument(
        "--db_path", 
        type=str, 
        default="./vector_db",
        help="Path to store the vector database"
    )
    parser.add_argument(
        "--chunk_size", 
        type=int, 
        default=1000,
        help="Size of text chunks"
    )
    parser.add_argument(
        "--chunk_overlap", 
        type=int, 
        default=200,
        help="Overlap between adjacent chunks"
    )
    
    args = parser.parse_args()
    
    process_pdf_folder(
        args.pdf_folder,
        args.db_path,
        args.chunk_size,
        args.chunk_overlap
    )

if __name__ == "__main__":
    main()