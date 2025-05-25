










import os
import sys
import argparse
import logging
from typing import List, Optional, Set
import datetime
import shutil
# import re # Not strictly needed with the revised metadata strategy

import dotenv
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS # Corrected FAISS import
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
    db_path: str,
    collection_name: str, # This will be used as the index_name for FAISS
    embedding_model_name: str,
    chunk_size: int,
    chunk_overlap: int,
):
    """
    Main function to load, process documents, and build/update the FAISS vector store.
    When a document is processed:
    1. Existing chunks in DB for the same original_filename with an older version_timestamp are deleted.
    2. New chunks are generated from the uploaded document.
    3. New chunks are assigned metadata:
        - source: unique ID like 'filename_timestamp_chunkIndex'
        - original_filename: base filename
        - version_timestamp: current processing timestamp
    4. These new versioned chunks are added to the database.
    """
    load_environment()

    logger.info("Initializing Google Generative AI Embeddings...")
    try:
        embeddings = GoogleGenerativeAIEmbeddings(model=embedding_model_name)
    except Exception as e:
        logger.critical(f"Failed to initialize embedding model: {e}", exc_info=True)
        sys.exit("Exiting due to embedding model initialization failure.")

    logger.info(f"Initializing/Loading FAISS index from: {db_path} with index name: {collection_name}")
    vector_db: Optional[FAISS] = None
    faiss_index_path = os.path.join(db_path, collection_name + ".faiss") # FAISS stores as folder/index_name.faiss

    if os.path.exists(faiss_index_path): # More robust check for FAISS index existence
        try:
            logger.info(f"Attempting to load existing FAISS index: {collection_name} from {db_path}")
            vector_db = FAISS.load_local(
                folder_path=db_path,
                embeddings=embeddings,
                index_name=collection_name,
                allow_dangerous_deserialization=True # Required for FAISS with LangChain
            )
            logger.info(f"Successfully loaded FAISS index '{collection_name}'.")
        except Exception as e:
            logger.error(f"Failed to load FAISS index '{collection_name}' from {db_path}: {e}. Will attempt to create a new one.", exc_info=True)
            vector_db = None # Ensure it's None if loading failed
    else:
        logger.info(f"FAISS index '{collection_name}.faiss' not found in {db_path}. A new index will be created if documents are processed.")
        vector_db = None

    logger.info(f"Scanning {docs_folder} for documents to process...")
    if not os.path.isdir(docs_folder):
        logger.error(f"Specified document folder does not exist: {docs_folder}")
        return

    total_chunks_added_this_run = 0
    processed_files_count = 0

    for doc_filename_in_temp_folder in os.listdir(docs_folder):
        original_file_full_path = os.path.join(docs_folder, doc_filename_in_temp_folder)
        
        if not os.path.isfile(original_file_full_path):
            logger.debug(f"Skipping non-file item: {doc_filename_in_temp_folder}")
            continue

        base_filename = doc_filename_in_temp_folder # This is the original name like "mydoc.pdf"
        current_processing_timestamp_str = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')

        logger.info(f"Processing document: {base_filename} with timestamp {current_processing_timestamp_str}")

        # --- Deletion Phase for older versions of this base_filename ---
        if vector_db: # Only attempt deletion if a DB is loaded
            ids_to_delete = []
            try:
                logger.debug(f"Checking for older versions of '{base_filename}' to delete from FAISS index.")
                # FAISS docstore is a dictionary of id -> Document
                # We need to iterate through it to find documents with matching 'original_filename'
                # and an older 'version_timestamp'.
                # The actual document IDs used by FAISS are in vector_db.index_to_docstore_id
                # And the documents (with metadata) are in vector_db.docstore._dict
                
                # Collect all doc IDs and their metadata
                candidate_ids_for_deletion = []
                for doc_id, doc_obj in vector_db.docstore._dict.items():
                    meta = doc_obj.metadata
                    if meta and meta.get("original_filename") == base_filename:
                        stored_version_timestamp = meta.get("version_timestamp")
                        if stored_version_timestamp and stored_version_timestamp < current_processing_timestamp_str:
                            candidate_ids_for_deletion.append(doc_id)
                            logger.debug(f"Marking for deletion (older version): FAISS ID {doc_id}, Source: {meta.get('source', 'N/A')}, Stored Timestamp: {stored_version_timestamp}")
                
                if candidate_ids_for_deletion:
                    # FAISS delete method expects a list of document IDs (the ones in docstore._dict.keys())
                    # It returns True if successful, False otherwise.
                    # Note: Deleting from FAISS can be complex and might not shrink the index file immediately.
                    # It marks entries for future overwrite or requires rebuilding for actual size reduction.
                    # Langchain's FAISS wrapper handles this.
                    logger.info(f"Found {len(candidate_ids_for_deletion)} older chunk(s) of '{base_filename}'. Attempting to delete them.")
                    delete_result = vector_db.delete(ids=candidate_ids_for_deletion)
                    if delete_result:
                        logger.info(f"Successfully deleted {len(candidate_ids_for_deletion)} older chunks for '{base_filename}' from FAISS index.")
                    else:
                        logger.warning(f"FAISS delete operation for {len(candidate_ids_for_deletion)} chunks of '{base_filename}' returned False. Some chunks may not have been deleted.")
                else:
                    logger.info(f"No older versions of chunks found for '{base_filename}' to delete in FAISS index.")

            except AttributeError as ae:
                 logger.error(f"Could not access FAISS docstore for deletion, vector_db might be None or not a FAISS instance: {ae}", exc_info=True)
            except Exception as e:
                logger.error(f"Error during FAISS deletion phase for {base_filename}: {e}", exc_info=True)
        else:
            logger.info(f"No FAISS database loaded, skipping deletion phase for {base_filename}.")

        # --- Loading and Processing New Document ---
        # Create a temporary directory for loading this single file to avoid issues with multi-file loaders
        temp_single_file_processing_dir = os.path.join(os.path.dirname(docs_folder), "_temp_single_file_processing")
        os.makedirs(temp_single_file_processing_dir, exist_ok=True)
        path_to_file_in_temp_single_dir = os.path.join(temp_single_file_processing_dir, base_filename)
        
        try:
            shutil.copy2(original_file_full_path, path_to_file_in_temp_single_dir)
            # loaded_docs_from_temp will have doc.metadata["source"] = absolute path of the copied file
            loaded_docs_from_temp = load_documents_from_folder(temp_single_file_processing_dir)
        finally:
            shutil.rmtree(temp_single_file_processing_dir)


        if not loaded_docs_from_temp:
            logger.warning(f"Could not load document {base_filename}. Skipping addition for this version.")
            continue
        
        # The 'source' in loaded_docs_from_temp is the path within temp_single_file_processing_dir.
        # This is fine as we are about to create new metadata.
        new_chunks_from_upload = split_documents_into_chunks(loaded_docs_from_temp, chunk_size, chunk_overlap)

        if not new_chunks_from_upload:
            logger.info(f"No chunks generated for {base_filename}. Skipping addition for this version.")
            continue

        # --- Preparing and Adding New Chunks to DB ---
        chunks_to_add_this_version = []
        for i, fresh_chunk in enumerate(new_chunks_from_upload):
            # fresh_chunk.metadata currently contains {'source': /path/in/_temp_single_file_processing/..., 'start_index': ...}
            
            chunk_unique_source_id = f"{base_filename}_{current_processing_timestamp_str}_{i}"
            
            final_metadata_for_chunk = {
                "source": chunk_unique_source_id,
                "original_filename": base_filename,
                "version_timestamp": current_processing_timestamp_str
            }
            if 'start_index' in fresh_chunk.metadata: # Preserve start_index
                final_metadata_for_chunk['start_index'] = fresh_chunk.metadata['start_index']
            # Potentially copy other relevant metadata from fresh_chunk.metadata if needed

            chunk_doc_to_add = Document(
                page_content=fresh_chunk.page_content,
                metadata=final_metadata_for_chunk
            )
            chunks_to_add_this_version.append(chunk_doc_to_add)

        if chunks_to_add_this_version:
            try:
                if vector_db is None: # Create new FAISS index
                    logger.info(f"Creating new FAISS index with {len(chunks_to_add_this_version)} chunks for '{base_filename}'.")
                    vector_db = FAISS.from_documents(chunks_to_add_this_version, embeddings)
                    logger.info(f"Successfully created new FAISS index and added {len(chunks_to_add_this_version)} chunks.")
                else: # Add to existing FAISS index
                    logger.info(f"Adding {len(chunks_to_add_this_version)} new chunks for '{base_filename}' to existing FAISS index.")
                    vector_db.add_documents(chunks_to_add_this_version)
                    logger.info(f"Successfully added {len(chunks_to_add_this_version)} new chunks.")
                total_chunks_added_this_run += len(chunks_to_add_this_version)
            except Exception as e:
                logger.error(f"Failed to add new chunks for {base_filename} (version: {current_processing_timestamp_str}) to FAISS: {e}", exc_info=True)
        else: 
            logger.info(f"No chunks were prepared to be added for {base_filename} (version: {current_processing_timestamp_str}).")
        
        processed_files_count += 1

    if vector_db and total_chunks_added_this_run > 0: # Only save if DB exists and chunks were added/updated
        try:
            logger.info(f"Saving FAISS index '{collection_name}' to {db_path}...")
            vector_db.save_local(folder_path=db_path, index_name=collection_name)
            logger.info(f"Successfully saved FAISS index '{collection_name}' to {db_path}.")
        except Exception as e:
            logger.error(f"Failed to save FAISS index '{collection_name}' to {db_path}: {e}", exc_info=True)
    elif vector_db and total_chunks_added_this_run == 0 and processed_files_count > 0:
        # This case handles when only deletions might have occurred.
        # FAISS deletions are in-memory until save.
        try:
            logger.info(f"Saving FAISS index '{collection_name}' to {db_path} after potential deletions...")
            vector_db.save_local(folder_path=db_path, index_name=collection_name)
            logger.info(f"Successfully saved FAISS index '{collection_name}' to {db_path} after potential deletions.")
        except Exception as e:
            logger.error(f"Failed to save FAISS index '{collection_name}' to {db_path} after potential deletions: {e}", exc_info=True)
    else:
        logger.info("No changes made to the FAISS index, or no index was created/loaded. Skipping save.")


    logger.info(f"Finished processing all documents. Added/updated a total of {total_chunks_added_this_run} versioned chunks from {processed_files_count} files processed in this run.")

# --- Command-Line Interface ---
def main():
    parser = argparse.ArgumentParser(description="RAG Knowledge Base Builder using Langchain and FAISS.")
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
        help="Name of the FAISS index (e.g., 'rag_main_collection'). Files will be 'rag_main_collection.faiss' and 'rag_main_collection.pkl'.",
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
