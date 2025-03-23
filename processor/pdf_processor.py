import os
import io
import fitz
import pytesseract
from PIL import Image
import ollama
import chromadb

# Constants
COLLECTION_NAME = "pdfs_collection"
PDF_FOLDER_PATH = "D:\\RAG\\RAG\\venv4\pdf"
doc_chunks = {}  # Store chunk-to-document mapping
collection = None

def initialize_pdf_collection():
    print("Initializing PDF collection...")
    global collection  # Ensure we're using the global variable
    
    try:
        client = ollama.Client()
        chroma_client = chromadb.Client()
        
        # Check if collection already exists
        try:
            # Try to get existing collection first
            collection = chroma_client.get_collection(COLLECTION_NAME)
            print(f"Using existing collection: {COLLECTION_NAME}")
            return collection  # Return the collection object
        except Exception as e:
            print(f"Collection doesn't exist yet: {e}")
            
            # Only try to delete if actually got an error from get_collection
            try:
                chroma_client.delete_collection(COLLECTION_NAME)
                print(f"Deleted existing collection: {COLLECTION_NAME}")
            except Exception as e:
                print(f"Error deleting collection (may not exist): {e}")

        # Create new collection
        collection = chroma_client.create_collection(COLLECTION_NAME)
        print(f"Created new collection: {COLLECTION_NAME}")

        # Check if PDF folder exists
        if not os.path.exists(PDF_FOLDER_PATH):
            print(f"Warning: PDF folder not found at {PDF_FOLDER_PATH}")
            return collection
            
        # Process PDFs
        for filename in os.listdir(PDF_FOLDER_PATH):
            if filename.endswith(".pdf"):
                pdf_path = os.path.join(PDF_FOLDER_PATH, filename)
                print(f"Processing PDF: {filename}")

                pdf_text = extract_text_from_pdf(pdf_path)
                if not pdf_text.strip():
                    print(f"No text found in {filename}. Skipping.")
                    continue

                chunks = split_text(pdf_text)
                print(f"Split PDF into {len(chunks)} chunks")

                # Add each chunk's text and embedding to the collection
                for i, chunk_text in enumerate(chunks, 1):
                    chunk_id = f"{filename}_chunk{i}"
                    embedding = get_embedding(chunk_text, client)
                    
                    # Double-check collection is not None before adding
                    if collection is None:
                        print("Error: Collection became None during processing")
                        collection = chroma_client.create_collection(COLLECTION_NAME)
                        
                    collection.add(
                        documents=[chunk_text],
                        embeddings=[embedding],
                        ids=[chunk_id],
                        metadatas=[{"source": filename}]  # Add metadata with source filename
                    )
                    doc_chunks[chunk_text] = filename  # Store the mapping
                    print(f"Added chunk {i} of {filename} to ChromaDB.")

        print("PDF collection initialization complete")
        return collection
        
    except Exception as e:
        print(f"Critical error during initialization: {e}")
        # Try to recreate the client and collection if an error occurred
        try:
            chroma_client = chromadb.Client()
            collection = chroma_client.create_collection(COLLECTION_NAME)
            print(f"Recreated collection after error")
            return collection
        except Exception as e2:
            print(f"Failed to recover from error: {e2}")
            return None

def split_text(text: str, max_chunk_size: int = 200) -> list:
    print("Starting text splitting...")
    chunks = []
    current_chunk = ""
    
    i = 0
    while i < len(text):
        current_chunk += text[i]
        i += 1
        
        if len(current_chunk) >= max_chunk_size:
            # Find appropriate split point
            if '.' in current_chunk:
                split_index = current_chunk.rfind('.') + 1
            elif ',' in current_chunk:
                split_index = current_chunk.rfind(',') + 1
            elif ' ' in current_chunk:
                split_index = current_chunk.rfind(' ')
            else:
                split_index = max_chunk_size
            
            chunks.append(current_chunk[:split_index].strip())
            current_chunk = current_chunk[split_index:].strip()

    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    print(f"Text split into {len(chunks)} chunks")
    return chunks

def extract_text_from_pdf(pdf_path: str) -> str:
    print(f"Extracting text from PDF: {pdf_path}")
    text = ""
    try:
        with fitz.open(pdf_path) as doc:
            for page_num, page in enumerate(doc, 1):
                print(f"Processing page {page_num}")
                text += page.get_text()
                for img_index, img in enumerate(page.get_images(full=True), start=1):
                    print(f"Processing image {img_index} on page {page_num}")
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    image = Image.open(io.BytesIO(image_bytes))
                    image_text = pytesseract.image_to_string(image)
                    text += f"\n[Image {img_index} Text]: {image_text}"
    except Exception as e:
        print(f"Error extracting text from {pdf_path}: {e}")
    return text

def get_embedding(text: str, client) -> list:
    print("Generating embedding...")
    result = client.embeddings(model="all-minilm", prompt=text)
    print("Embedding generated successfully")
    return result['embedding']

def get_llama_response(context: str, query: str, output_language: str, client) -> str:
    print("Generating Llama response...")
    prompt = f"""You are a helpful AI assistant. Use the following context to answer the question provided.
    Give the response in {output_language} language.
   
    Context:
    {context}
   
    Question:
    {query}
   
    Answer based on the context:"""
    try:
        response = client.chat(
            model="llama_rag_model:latest",
            messages=[
                {"role": "system", "content": "You are a helpful AI assistant."},
                {"role": "user", "content": prompt}
            ],
            stream=False
        )
        print("Llama response generated successfully")
        return response.get("message", {}).get("content", "").strip()
    except Exception as e:
        print(f"Error with Llama3.2 API: {e}")
        return "No response received from Llama3.2."