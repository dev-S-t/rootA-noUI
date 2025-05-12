import requests
import os
from requests.auth import HTTPBasicAuth
import logging  # Added for direct RAG testing

# Imports for direct RAG testing
from multi_tool_agent.agent import rag_answer as direct_rag_answer
import multi_tool_agent.agent as agent_module

BASE_URL = "http://localhost:8000"  # Assuming your FastAPI app runs on port 8000
USER = "testuserapi"
PASSWORD = "testpassapi"  # From users.json
RAG_NAME = USER  # Assuming RAG name is the same as the username for this test

FILE_TO_UPLOAD_NAME = ".NET_MVVM_(New)_.NETMVVMNew.pdf"
FILE_TO_UPLOAD_PATH_RELATIVE = os.path.join("pdfs", FILE_TO_UPLOAD_NAME)
# Construct absolute path from the script's location or a known base
# For this example, assuming the script is run from /workspaces/rootA-noUI/
FILE_TO_UPLOAD_ABSOLUTE_PATH = os.path.abspath(FILE_TO_UPLOAD_PATH_RELATIVE)


def upload_file():
    print(f"--- Attempting to upload {FILE_TO_UPLOAD_NAME} for user {USER} ---")
    if not os.path.exists(FILE_TO_UPLOAD_ABSOLUTE_PATH):
        print(f"ERROR: File not found at {FILE_TO_UPLOAD_ABSOLUTE_PATH}")
        return False

    upload_url = f"{BASE_URL}/upload/{USER}"
    files = {'files': (FILE_TO_UPLOAD_NAME, open(FILE_TO_UPLOAD_ABSOLUTE_PATH, 'rb'), 'application/pdf')}
    
    # No custom_instructions needed for this test, but the endpoint expects the field
    data = {'custom_instructions': ''}

    try:
        response = requests.post(upload_url, files=files, data=data, auth=HTTPBasicAuth(USER, PASSWORD), timeout=30)
        response.raise_for_status()  # Raise an exception for HTTP errors
        print("Upload Response JSON:", response.json())
        if response.json().get("uploaded_files") and FILE_TO_UPLOAD_NAME in response.json()["uploaded_files"]:
            print(f"File {FILE_TO_UPLOAD_NAME} uploaded successfully to temp location.")
            return True
        else:
            print(f"File {FILE_TO_UPLOAD_NAME} upload failed or not listed in response.")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Error during file upload: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response content: {e.response.text}")
        return False

def process_documents():
    print(f"--- Attempting to process documents for user {USER} ---")
    process_url = f"{BASE_URL}/process_docs/{USER}"
    try:
        response = requests.post(process_url, auth=HTTPBasicAuth(USER, PASSWORD), timeout=120)  # Increased timeout
        response.raise_for_status()
        print("Process Documents Response JSON:", response.json())
        if "error" not in response.json():
            print("Documents processed successfully.")
            return True
        else:
            print(f"Error processing documents: {response.json().get('error')}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"Error during document processing: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response content: {e.response.text}")
        return False

def rag_search(query: str):
    print(f"--- Attempting DIRECT RAG search for query: '{query}' on RAG '{RAG_NAME}' ---")
    
    original_active_rag_name = agent_module.ACTIVE_RAG_NAME
    agent_module.ACTIVE_RAG_NAME = RAG_NAME
    # Configure basic logging to see output from the agent module if it uses Python's logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.info(f"Set agent_module.ACTIVE_RAG_NAME to: {agent_module.ACTIVE_RAG_NAME} for direct RAG search.")

    try:
        # Call the rag_answer function directly from the agent module
        search_result = direct_rag_answer(question=query)
        
        print(f"Direct RAG Search Raw Result for RAG '{RAG_NAME}':", search_result)

        if search_result and isinstance(search_result, dict):
            status = search_result.get("status")
            answer = search_result.get("answer")
            error_message = search_result.get("error_message")

            if status == "success":
                print("Direct RAG search successful.")
                print("Retrieved Answer/Context:", answer)
            elif status == "partial_success":
                print("Direct RAG search resulted in partial success (e.g., fallback).")
                print("Details:", answer)
            elif status == "no_matches_found":
                print("Direct RAG search found no matching documents.")
                print("Details:", answer)
            elif status == "error":
                print(f"Direct RAG search encountered an error: {error_message}")
            else:
                print(f"Direct RAG search returned an unknown status: {status}")
                print("Full response:", search_result)
        else:
            print("Direct RAG search returned an unexpected result format:", search_result)

    except Exception as e:
        logger.error(f"Exception during direct RAG search: {e}", exc_info=True)
        print(f"Error during direct RAG search: {e}")
    finally:
        # Restore original RAG name
        agent_module.ACTIVE_RAG_NAME = original_active_rag_name
        logger.info(f"Restored agent_module.ACTIVE_RAG_NAME to: {agent_module.ACTIVE_RAG_NAME}")

if __name__ == "__main__":
    print(f"Starting MVVM RAG retrieval test for user: {USER}")
    print(f"Target file: {FILE_TO_UPLOAD_ABSOLUTE_PATH}")

    # Step 1: Upload the file
    if upload_file():
        # Step 2: Process the documents
        if process_documents():
            # Step 3: Perform RAG search
            # Adding a small delay to ensure processing is complete, though the API should be synchronous
            import time
            print("Waiting 5 seconds before RAG search...")
            time.sleep(5)
            rag_search(query=".net mvvm")
        else:
            print("Skipping RAG search due to document processing failure.")
    else:
        print("Skipping document processing and RAG search due to upload failure.")
    
    print("--- Test script finished ---")
