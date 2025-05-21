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
import datetime # Added import
import shutil # Added import

import dotenv
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
import chromadb # Added import
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
def load_documents_from_folder(folder_path: str) -> List[Document]:
    """
    Loads all documents from PDF and DOCX files in the specified folder.
    The source metadata for each document is set to its absolute file path.
    """
    loaded_docs: List[Document] = []
    logger.info(f"Scanning document folder for loading: {folder_path}")

    if not os.path.isdir(folder_path):
        logger.error(f"Specified document folder does not exist: {folder_path}")
        return loaded_docs

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        abs_file_path = os.path.abspath(file_path) # Use absolute path for consistent source tracking

        if not os.path.isfile(file_path):
            logger.debug(f"Skipping non-file item: {filename}")
            continue

        # Removed processed_sources check, as we now delete then add for updates.
        # All files found will be loaded.

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
    db_path: str, # This will now be custom_rag/db_name
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
        embedding_function=embeddings,
        client_settings=chromadb.config.Settings( # Explicit client settings
            is_persistent=True,
            persist_directory=db_path,
            anonymized_telemetry=False # Consistent with logs
        )
    )

    logger.info(f"Scanning {docs_folder} for documents to process...")
    if not os.path.isdir(docs_folder):
        logger.error(f"Specified document folder does not exist: {docs_folder}")
        return

    all_new_versioned_chunks_added_count = 0
    processed_files_count = 0

    for filename in os.listdir(docs_folder): # docs_folder is like ".../s_temp_uploads"
        original_file_path_in_temp_uploads = os.path.join(docs_folder, filename)
        original_source_id = os.path.abspath(original_file_path_in_temp_uploads)

        if not os.path.isfile(original_file_path_in_temp_uploads):
            logger.debug(f"Skipping non-file item: {filename}")
            continue

        logger.info(f"Processing document: {filename} (original source ID: {original_source_id})")

        # Create temp dir for single file processing
        temp_single_file_dir = os.path.join(os.path.dirname(docs_folder), "_temp_single_file_processing")
        os.makedirs(temp_single_file_dir, exist_ok=True)
        path_to_file_in_temp_single_dir = os.path.join(temp_single_file_dir, filename)
        shutil.copy2(original_file_path_in_temp_uploads, path_to_file_in_temp_single_dir)

        loaded_docs_from_temp = load_documents_from_folder(temp_single_file_dir)
        shutil.rmtree(temp_single_file_dir)

        if not loaded_docs_from_temp:
            logger.warning(f"Could not load document {filename}. Skipping.")
            continue
        
        # CRITICAL STEP: Correct the source metadata on the loaded documents BEFORE chunking
        for doc_obj in loaded_docs_from_temp:
            doc_obj.metadata["source"] = original_source_id

        new_chunks_from_upload = split_documents_into_chunks(loaded_docs_from_temp, chunk_size, chunk_overlap)

        if not new_chunks_from_upload:
            logger.info(f"No chunks generated for {filename}. Skipping.")
            continue

        # Fetch existing page_contents for the ORIGINAL source ID
        existing_page_contents_for_original_source = set()
        try:
            logger.debug(f"Fetching existing chunk documents for original source: {original_source_id}")
            existing_data = vector_db.get(where={"source": original_source_id}, include=["documents"])
            if existing_data and existing_data.get("documents"):
                for content in existing_data["documents"]:
                    if content is not None:
                        existing_page_contents_for_original_source.add(content)
                logger.info(f"Found {len(existing_page_contents_for_original_source)} existing unique page_contents for original source: {original_source_id}")
            else:
                logger.info(f"No existing chunk documents found for original source: {original_source_id}")
        except Exception as e:
            logger.error(f"Error fetching existing content for {original_source_id}: {e}", exc_info=True)
            continue

        chunks_to_add_with_versioned_ids = []
        timestamp_str = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
        
        for i, fresh_chunk in enumerate(new_chunks_from_upload):
            if fresh_chunk.page_content not in existing_page_contents_for_original_source:
                versioned_source_id = f"{original_source_id}#v{timestamp_str}_{i}"
                logger.debug(f"New/modified content found. Assigning versioned_source_id: {versioned_source_id}")
                
                versioned_chunk_doc = Document(
                    page_content=fresh_chunk.page_content,
                    metadata={**fresh_chunk.metadata, "source": versioned_source_id} 
                )
                chunks_to_add_with_versioned_ids.append(versioned_chunk_doc)
            # else: logger.debug(f"Chunk content for {original_source_id} already exists. Skipping.")

        if chunks_to_add_with_versioned_ids:
            try:
                vector_db.add_documents(chunks_to_add_with_versioned_ids)
                logger.info(f"Successfully added {len(chunks_to_add_with_versioned_ids)} new/modified chunks for original source {original_source_id} with versioned IDs.")
                all_new_versioned_chunks_added_count += len(chunks_to_add_with_versioned_ids)
            except Exception as e:
                logger.error(f"Failed to add versioned chunks for {original_source_id} to ChromaDB: {e}", exc_info=True)
        else:
            logger.info(f"No new or modified content found for original source {original_source_id} to add.")
        processed_files_count +=1

    logger.info(f"Finished processing all documents. Added a total of {all_new_versioned_chunks_added_count} new/modified versioned chunks from {processed_files_count} files.")

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
        "--db_name",
        type=str,
        default="default_rag",
        help="Name of the database. This will be created as a subfolder within 'custom_rag'.",
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

    # Construct the actual database path inside custom_rag folder
    base_db_dir = "custom_rag"
    actual_db_path = os.path.join(base_db_dir, args.db_name)

    # Create custom_rag and custom_rag/db_name directories if they don't exist
    if not os.path.exists(base_db_dir):
        logger.info(f"Base database directory '{base_db_dir}' not found. Creating it.")
        os.makedirs(base_db_dir)
    
    if not os.path.exists(actual_db_path):
        logger.info(f"Database directory '{actual_db_path}' not found. Creating it.")
        os.makedirs(actual_db_path)
    
    logger.info(f"Using database at path: {actual_db_path}")

    process_documents_and_build_db(
        docs_folder=args.docs_folder,
        db_path=actual_db_path, # Use the constructed path
        collection_name=args.collection_name,
        embedding_model_name=args.embedding_model,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

if __name__ == "__main__":
    main()