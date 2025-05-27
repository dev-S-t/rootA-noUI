# KnowledgePilot: Intelligent RAG & Generative AI Agent

KnowledgePilot is a high-performance FastAPI application engineered to transform document interaction through advanced AI capabilities. Built upon **Google's Agent Development Kit (ADK)**, this project showcases the rapid development and deployment of sophisticated AI features, including the development of a sophisticated Retrieval Augmented Generation (RAG) system for building custom knowledge bases from PDF and DOCX files, leveraging FAISS and Langchain for optimal performance. KnowledgePilot also integrates Google Generative AI for state-of-the-art text generation and comprehension, and implements a versatile multi-tool AI agent designed for complex task execution.

## Key AI/ML Features

### Customizable RAG System
- **Seamless Document Ingestion:** Engineered a robust system for users to upload PDF and DOCX documents, forming the backbone of personalized knowledge repositories.
- **Automated Knowledge Base Construction:** Developed an automated pipeline that processes and structures uploaded documents into custom knowledge bases, enabling intelligent and context-aware information retrieval.
- **High-Efficiency Retrieval & Orchestration:** Implemented FAISS for rapid, high-precision similarity searches across document vectors and leveraged Langchain for sophisticated orchestration of the end-to-end RAG pipeline.
- **Dynamic Contextual Interaction:** Engineered the RAG system to support dynamic, contextual conversations, empowering users to extract nuanced insights and precise answers from their document collections.

### Google Generative AI Integration
- **State-of-the-Art Generative Capabilities:** Integrated Google's cutting-edge generative AI models to significantly enhance a wide array of text-based tasks.
- **Advanced NLP Applications:** Leveraged generative models for sophisticated text generation, intelligent summarization of RAG-retrieved information, and in-depth, context-aware question answering.

### Multi-Tool AI Agent (Powered by Google ADK)
- **Intelligent Agent Design:** Developed an intelligent agent equipped with a versatile toolkit, enabling it to perform a diverse range of functions and actions. This agent is engineered using **Google's Agent Development Kit (ADK)**, a comprehensive toolkit that provides a robust and scalable framework for defining, managing, and executing complex, **multi-tool** agentic behaviors. The ADK significantly streamlines development and facilitates seamless integration with Google's AI ecosystem, enhancing its sophisticated task decomposition and execution capabilities.
- **Sophisticated Task Decomposition & Execution:** Engineered the agent to autonomously break down and execute complex, multi-step tasks, demonstrating advanced problem-solving capabilities beyond basic query responses.
- **Autonomous System Interaction:** The multi-tool agent elevates the application's sophistication, facilitating more autonomous and nuanced interactions with both the system and user data.

## How It Works

The application implements a sophisticated Retrieval Augmented Generation (RAG) pipeline:
1.  **Document Upload:** Users securely upload PDF and DOCX documents via the API.
2.  **Processing & Embedding:** Documents undergo automated processing: text extraction, content chunking, and conversion into high-dimensional vector embeddings using advanced sentence transformer models. These embeddings are indexed within a FAISS vector store, creating a specialized knowledge base.
3.  **User Interaction & Retrieval:** Upon receiving a user prompt, the system performs a semantic search against the FAISS vector store to retrieve the most relevant document chunks.
4.  **Context-Aware Response Generation:** The retrieved contextual information is then synthesized with the original user prompt and fed into a Google Generative AI model, which generates a comprehensive and contextually accurate response.

## Technologies Used

- **Backend Framework:** FastAPI (Chosen for its high performance and asynchronous capabilities, ideal for AI/ML workloads)
- **Core AI Framework:** Google ADK (Agent Development Kit) - Leveraged as the foundational framework for **efficiently** building, deploying, and managing the application's intelligent agents. It facilitates seamless interaction with various tools and Google's Generative AI models, significantly accelerating the development lifecycle.
- **Programming Language:** Python (The de facto standard for AI/ML development)
- **AI/ML Orchestration:** Langchain (For robust and flexible RAG pipeline construction and agent management)
- **Generative AI:** Google Generative AI (Leveraging state-of-the-art models for advanced NLP tasks)
- **Vector Store & Similarity Search:** FAISS (cpu) (For efficient and scalable semantic search over document embeddings)
- **Document Processing:**
    - pypdf (For PDF text extraction)
    - docx2txt (For DOCX text extraction)
- **Web Server:** Uvicorn (ASGI server for FastAPI)
- **Core Libraries & Tools:**
    - `langchain-community`, `langchain-core`, `langchain-google-genai`, `langchain-text-splitters`, `langchain-faiss`
    - `google-generativeai`
    - `python-dotenv` (For secure environment configuration management)
    - `python-multipart` (For handling file uploads in FastAPI)

## Key API Endpoints

The application exposes the following key API endpoints, built with FastAPI:

-   `POST /signup`: Enables new user registration.
-   `POST /upload/{user_name}`: Allows registered users to upload PDF/DOCX documents and define custom RAG instructions.
-   `POST /process_docs/{user_name}`: Initiates the processing of uploaded documents to build or update the user-specific RAG vector database.
-   `POST /run` (and `POST /run/{user_rag_name}`): Facilitates user interaction with the AI agent, leveraging the RAG system and Google Generative AI for response generation.
-   `POST /run_sse` (and `POST /run_sse/{user_rag_name}`): Provides Server-Sent Events (SSE) for real-time, streaming responses from the AI agent.

## Setup and Usage (Basic)

This application is built using FastAPI and requires Python 3.9+.

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```
2.  **Install dependencies:**
    Ensure you have Python installed. Then, install the required packages:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Environment Configuration:**
    Create a `.env` file in the project root (refer to `.env.example` if available, or create one based on required settings like `GOOGLE_API_KEY`). Populate it with necessary environment variables, including API keys for Google Generative AI.
4.  **Run the application:**
    ```bash
    uvicorn main:app --reload
    ```
    The application will typically be available at `http://127.0.0.1:8000`.

## Future Work & Potential Enhancements

This project lays a strong foundation for further development. Potential future enhancements include:

-   **Expanded Document Support:** Incorporating support for additional document formats such as `.txt`, `.md`, and `.csv` to enable Q&A over structured data.
-   **Diverse AI Service Integration:** Integrating with a broader range of specialized AI services or APIs (e.g., financial data APIs, scientific research databases) to enrich the agent's knowledge domain.
-   **Advanced Agentic Workflows:** Developing more sophisticated and autonomous agentic workflows, allowing the agent to handle even more complex, multi-step reasoning and tool usage.
-   **Enhanced User Interface (UI/UX):** Designing and implementing a more interactive and user-friendly interface for easier knowledge base management, agent interaction, and visualization of results.
-   **Advanced RAG Techniques:** Implementing cutting-edge RAG strategies such as query rewriting for clarity, hybrid search (combining semantic and keyword search), and re-ranking of retrieved results for improved relevance.
-   **Fine-tuning Embedding Models:** Exploring the fine-tuning of embedding models on domain-specific data to further improve the accuracy and relevance of the RAG system.