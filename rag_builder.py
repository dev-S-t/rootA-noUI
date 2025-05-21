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
from typing import List, Optional
from collections import defaultdict

import dotenv
import chromadb # Added import
import requests # Added for Render API
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
def load_documents_from_folder(folder_path: str) -> List[Document]:
    """
    Loads documents from PDF and DOCX files in the specified folder.
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
    Implements metadata-driven deletion: if a file with the same name is re-uploaded, old chunks are removed before new ones are added.
    """
    load_environment()

    logger.info("Initializing Google Generative AI Embeddings...")
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model=embedding_model_name)
    except Exception as e:
        logger.critical(f"Failed to initialize embedding model: {e}", exc_info=True)
        sys.exit("Exiting due to embedding model initialization failure.")

    logger.info(f"Initializing ChromaDB client for path: {db_path}")
    vector_db: Chroma
    try:
        # Create a persistent client
        client = chromadb.PersistentClient(path=db_path)
        
        logger.info(f"Initializing Langchain Chroma wrapper for collection: {collection_name} using the client.")
        # The Langchain Chroma wrapper will use this client to interact with the specified collection.
        # It will create the collection if it doesn't exist, using the provided embedding function.
        vector_db = Chroma(
            client=client,
            collection_name=collection_name,
            embedding_function=embeddings,
        )
        # Log count using the Langchain Chroma wrapper's internal collection object
        initial_count = vector_db._collection.count()
        logger.info(f"ChromaDB connection established. Collection '{collection_name}' initial count: {initial_count}")

    except Exception as e:
        logger.critical(f"Failed to initialize ChromaDB client or Langchain wrapper: {e}", exc_info=True)
        sys.exit("Exiting due to ChromaDB initialization failure.")

    new_documents = load_documents_from_folder(docs_folder)

    if not new_documents:
        logger.info("No new documents found to process or load from the folder.")
        return

    any_replacement_occurred = False # Flag to track if any document replacement happened

    # --- Metadata-driven deletion and chunking ---
    # Group documents by filename
    docs_by_filename = defaultdict(list)
    for doc in new_documents:
        # Use just the filename (not full path) for matching
        file_name = os.path.basename(doc.metadata.get("source", ""))
        doc.metadata["source_file_name"] = file_name
        docs_by_filename[file_name].append(doc)

    for file_name, docs in docs_by_filename.items():
        # Delete all existing chunks for this file_name
        logger.info(f"[RAG-REPLACE] Deleting existing chunks for file: {file_name} in collection '{collection_name}'...")
        count_before_delete = vector_db._collection.count()
        logger.info(f"[RAG-REPLACE] Count before delete for '{file_name}': {count_before_delete}")
        try:
            # It's important to ensure that the client associated with vector_db is the one performing operations.
            # The Langchain Chroma wrapper's delete method should handle this.
            # We are deleting based on metadata that should be unique to the file's chunks.
            ids_to_delete = []
            # To be absolutely sure, one could fetch IDs based on the where clause first, then delete by ID.
            # However, delete with a where clause should work.
            # Let's get the documents first to see what Chroma thinks matches, then try to delete their IDs.
            # This is for more robust deletion.
            
            # Get existing documents matching the source_file_name
            existing_docs_for_file = vector_db._collection.get(
                where={"source_file_name": file_name},
                include=["metadatas"] # Corrected: removed backslashes
            )
            ids_to_delete = existing_docs_for_file['ids']

            if ids_to_delete:
                logger.info(f"[RAG-REPLACE] Found {len(ids_to_delete)} chunk IDs to delete for file: {file_name}. IDs: {ids_to_delete}")
                vector_db._collection.delete(ids=ids_to_delete) # Using direct collection delete by IDs
                logger.info(f"[RAG-REPLACE] Successfully submitted deletion for {len(ids_to_delete)} IDs for '{file_name}'.")
                any_replacement_occurred = True # A replacement occurred for this file
            else:
                logger.info(f"[RAG-REPLACE] No existing chunk IDs found to delete for file: {file_name} based on metadata query.")

            # del_result = vector_db.delete(where={\"source_file_name\": file_name}) # Old way
            # logger.info(f\"[RAG-REPLACE] Delete result for \'{file_name}\': {del_result}\")


        except Exception as e:
            logger.error(f"[RAG-REPLACE] Error during deletion process for '{file_name}': {e}", exc_info=True)
        
        count_after_delete = vector_db._collection.count()
        logger.info(f"[RAG-REPLACE] Count after delete for '{file_name}': {count_after_delete}")

        # Split and add new chunks
        chunks = split_documents_into_chunks(docs, chunk_size, chunk_overlap)
        if chunks:
            # Ensure all chunks have the correct source_file_name metadata and valid page_content
            for i, chunk in enumerate(chunks):
                chunk.metadata["source_file_name"] = file_name
                if not isinstance(chunk.page_content, str):
                    logger.warning(f"[RAG-REPLACE] Chunk {i} for file '{file_name}' has non-string page_content (type: {type(chunk.page_content)}). Converting to empty string. Content: '{chunk.page_content!r}'")
                    chunk.page_content = str(chunk.page_content) if chunk.page_content is not None else ""
                # Log a snippet of page_content and its type
                # logger.debug(f"[RAG-REPLACE] Chunk {i} for \'{file_name}\' to be added. Metadata: {chunk.metadata}, Page Content Type: {type(chunk.page_content)}, Snippet: \'{chunk.page_content[:100]}...\'")


            logger.info(f"[RAG-REPLACE] Adding {len(chunks)} new chunks for file: {file_name} to the vector store...")
            try:
                vector_db.add_documents(chunks) # Langchain wrapper's add_documents
                logger.info(f"[RAG-REPLACE] Successfully submitted add_documents for {len(chunks)} chunks for '{file_name}'.")
            except Exception as e:
                logger.error(f"[RAG-REPLACE] Failed to add chunks for '{file_name}' to ChromaDB: {e}", exc_info=True) # Corrected: f-string properly terminated
            
            count_after_add = vector_db._collection.count()
            logger.info(f"[RAG-REPLACE] Count after add for '{file_name}': {count_after_add}")

    if any_replacement_occurred:
        logger.info("[RAG-BUILDER] Document replacement occurred. Attempting to trigger Render service restart via API.")
        try:
            service_id = os.getenv("RENDER_SERVICE_ID")
            api_token = os.getenv("RENDER_API_TOKEN")

            if not service_id:
                logger.warning("[RAG-BUILDER] RENDER_SERVICE_ID environment variable not set. Cannot trigger Render restart.")
            elif not api_token:
                logger.warning("[RAG-BUILDER] RENDER_API_TOKEN environment variable not set. Cannot trigger Render restart.")
            else:
                restart_url = f"https://api.render.com/v1/services/{service_id}/restart"
                headers = {
                    "Authorization": f"Bearer {api_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json" 
                }
                
                logger.info(f"[RAG-BUILDER] Sending POST request to Render restart API: {restart_url}")
                response = requests.post(restart_url, headers=headers)
                
                if 200 <= response.status_code < 300:
                    logger.info(f"[RAG-BUILDER] Successfully triggered Render service restart. Status: {response.status_code}, Response: {response.text}")
                else:
                    logger.error(f"[RAG-BUILDER] Failed to trigger Render service restart. Status: {response.status_code}, Response: {response.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"[RAG-BUILDER] Error calling Render API to trigger restart: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"[RAG-BUILDER] An unexpected error occurred while trying to trigger Render restart: {e}", exc_info=True)
    else:
        logger.info("[RAG-BUILDER] No document replacements occurred. Skipping Render service restart.")

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