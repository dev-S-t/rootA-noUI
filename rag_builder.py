try:
    __import__('pysqlite3')
    import sys
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
    print("Successfully patched sqlite3 with pysqlite3.")
except ImportError:
    print("pysqlite3 not found, using system sqlite3. This might lead to errors with ChromaDB.")
except KeyError:
    print("pysqlite3 was imported but an issue occurred patching sys.modules.")











import os
import sys
import argparse
import logging
from typing import List, Optional, Set

import dotenv
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
# The google.generativeai package will be imported by langchain_google_genai
# but we might need to import it directly if we were to use genai.configure explicitly
# For now, langchain_google_genai handles API key from environment variable.

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# --- Environment Loading ---
def load_environment():
    """Loads environment variables from .env file and checks for GOOGLE_API_KEY."""
    logger.info("Loading environment variables...")
    dotenv.load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.error("GOOGLE_API_KEY not found in environment variables or .env file.")
        sys.exit("Error: GOOGLE_API_KEY is not set.")
    # langchain_google_genai will pick up the API key from the environment.
    # If explicit configuration was needed:
    # import google.generativeai as genai
    # genai.configure(api_key=api_key)
    logger.info("GOOGLE_API_KEY loaded successfully.")
    return api_key

# --- Document Processing ---
def load_documents_from_folder(folder_path: str, processed_sources: Set[str]) -> List[Document]:
    """
    Loads documents from PDF and DOCX files in the specified folder,
    skipping files whose source path is already in processed_sources.
    """
    loaded_docs: List[Document] = []
    logger.info(f"Scanning document folder: {folder_path}")

    if not os.path.isdir(folder_path):
        logger.error(f"Specified document folder does not exist: {folder_path}")
        return loaded_docs

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        abs_file_path = os.path.abspath(file_path) # Use absolute path for consistent source tracking

        if not os.path.isfile(file_path):
            logger.debug(f"Skipping non-file item: {filename}")
            continue

        if abs_file_path in processed_sources:
            logger.info(f"Skipping already processed file: {filename}")
            continue

        loader: Optional[PyPDFLoader | Docx2txtLoader] = None
        doc_type = ""

        if filename.lower().endswith(".pdf"):
            loader = PyPDFLoader(file_path)
            doc_type = "PDF"
        elif filename.lower().endswith(".docx"):
            loader = Docx2txtLoader(file_path)
            doc_type = "DOCX"
        else:
            logger.warning(f"Unsupported file type: {filename}. Skipping.")
            continue

        try:
            logger.info(f"Loading {doc_type}: {filename}...")
            new_docs = loader.load()
            # Ensure source metadata reflects the absolute path for uniqueness
            for doc in new_docs:
                doc.metadata["source"] = abs_file_path
            loaded_docs.extend(new_docs)
            logger.info(f"Successfully loaded {len(new_docs)} pages/sections from {filename}.")
        except Exception as e:
            logger.error(f"Failed to load {filename}: {e}", exc_info=True)

    return loaded_docs

def split_documents_into_chunks(
    documents: List[Document], chunk_size: int, chunk_overlap: int
) -> List[Document]:
    """Splits loaded documents into smaller chunks using RecursiveCharacterTextSplitter."""
    if not documents:
        logger.info("No documents to split.")
        return []

    logger.info(f"Splitting {len(documents)} document pages/sections into chunks (size: {chunk_size}, overlap: {chunk_overlap})...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        add_start_index=True, # Helpful for context or if IDs need to be more unique
    )
    chunks = text_splitter.split_documents(documents)
    logger.info(f"Generated {len(chunks)} chunks from the documents.")
    return chunks

# --- Main Application Logic ---
def process_documents_and_build_db(
    docs_folder: str,
    db_path: str,
    collection_name: str,
    embedding_model_name: str,
    chunk_size: int,
    chunk_overlap: int,
):
    """
    Main function to load, process documents, and build/update the ChromaDB vector store.
    """
    load_environment()

    logger.info("Initializing Google Generative AI Embeddings...")
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model=embedding_model_name)
    except Exception as e:
        logger.critical(f"Failed to initialize embedding model: {e}", exc_info=True)
        sys.exit("Exiting due to embedding model initialization failure.")

    logger.info(f"Initializing/Loading ChromaDB from: {db_path} with collection: {collection_name}")
    vector_db = Chroma(
        collection_name=collection_name,
        persist_directory=db_path,
        embedding_function=embeddings,
    )

    # Get sources already in the DB to avoid re-processing
    processed_sources: Set[str] = set()
    try:
        existing_docs = vector_db.get(include=["metadatas"])
        if existing_docs and existing_docs.get("metadatas"):
            for metadata in existing_docs["metadatas"]:
                if metadata and "source" in metadata:
                    processed_sources.add(metadata["source"])
        logger.info(f"Found {len(processed_sources)} sources already processed in the database.")
    except Exception as e: # Broad exception if collection doesn't exist or other DB issues
        logger.warning(f"Could not retrieve existing sources from DB (collection might be new or empty): {e}")


    new_documents = load_documents_from_folder(docs_folder, processed_sources)

    if not new_documents:
        logger.info("No new documents found to process or load from the folder.")
        return

    chunks = split_documents_into_chunks(new_documents, chunk_size, chunk_overlap)

    if chunks:
        logger.info(f"Adding {len(chunks)} new chunks to the vector store...")
        try:
            # Langchain's default Document objects from loaders get UUIDs, so re-adding the
            # same content (if not skipped by source check) will create new entries.
            # If specific ID management is needed for updates, that's a more complex step.
            vector_db.add_documents(chunks)
            logger.info("Successfully added new chunks to the database.")
        except Exception as e:
            logger.error(f"Failed to add chunks to ChromaDB: {e}", exc_info=True)
            return

# --- Command-Line Interface ---
def main():
    parser = argparse.ArgumentParser(description="RAG Knowledge Base Builder using Langchain and ChromaDB.")
    parser.add_argument(
        "--docs_folder",
        type=str,
        default="docs",
        help="Path to the folder containing PDF and DOCX documents to process.",
    )
    parser.add_argument(
        "--db_path",
        type=str,
        default="./chroma_rag_db",
        help="Path to the directory where ChromaDB should be persisted.",
    )
    parser.add_argument(
        "--collection_name",
        type=str,
        default="rag_main_collection",
        help="Name of the collection within ChromaDB.",
    )
    parser.add_argument(
        "--embedding_model",
        type=str,
        default="models/embedding-001",
        help="Name of the Google Generative AI embedding model to use.",
    )
    parser.add_argument(
        "--chunk_size", type=int, default=1000, help="Size of text chunks for splitting documents."
    )
    parser.add_argument(
        "--chunk_overlap", type=int, default=200, help="Overlap between text chunks."
    )
    parser.add_argument(
        "--env_file", type=str, default=None, help="Path to .env file (optional, uses os.environ by default)."
    )

    args = parser.parse_args()

    # Load specific .env file if provided, otherwise dotenv loads default .env
    if args.env_file:
        logger.info(f"Loading .env file from specified path: {args.env_file}")
        dotenv.load_dotenv(dotenv_path=args.env_file, override=True)
    else:
        logger.info("Attempting to load .env file from default location (if it exists).")
        dotenv.load_dotenv(override=True) # Load default .env, override os.environ if keys exist


    # Create docs_folder if it doesn't exist, with a message
    if not os.path.exists(args.docs_folder):
        logger.info(f"Documents folder '{args.docs_folder}' not found. Creating it.")
        os.makedirs(args.docs_folder)
        logger.info(f"Please add your PDF and DOCX files to '{args.docs_folder}' and re-run.")
        return # Exit if folder was just created, as it will be empty

    process_documents_and_build_db(
        docs_folder=args.docs_folder,
        db_path=args.db_path,
        collection_name=args.collection_name,
        embedding_model_name=args.embedding_model,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

if __name__ == "__main__":
    main()