import os
from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone
import uuid
from typing import List

# --- Configuration ---
DIMENSION = 512  # for text-embedding-3-small
CHUNK_SIZE = 300  # characters per chunk

# --- Load API keys ---
load_dotenv()
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- Initialize clients ---
pc = Pinecone(api_key=PINECONE_API_KEY)
client = OpenAI(api_key=OPENAI_API_KEY)


def get_embedding(text: str) -> List[float]:
    """Generate embedding for text using OpenAI (512-dimension model)"""
    try:
        response = client.embeddings.create(
            input=text,
            model="text-embedding-3-small",
            dimensions=DIMENSION
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")
        return []


def split_text_into_chunks(text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
    """Split text into chunks of specified size"""
    # Validate input text
    if not text or text is None:
        return []
    
    # Convert to string and strip whitespace
    text = str(text).strip()
    if not text:
        return []
    
    chunks = []
    words = text.split()
    current_chunk = []
    current_length = 0

    for word in words:
        # Skip None or empty words
        if word is None or not word:
            continue
            
        word = str(word)  # Ensure word is string
        if current_length + len(word) + 1 <= chunk_size:
            current_chunk.append(word)
            current_length += len(word) + 1
        else:
            if current_chunk:
                chunks.append(' '.join(current_chunk))
            current_chunk = [word]
            current_length = len(word)

    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks


def upload_data_to_index(
        index: str, text: str, type: str, platform_user_id: str,
        provider_id: str, platform: str) -> bool:
    """Upload text data to Pinecone index with metadata"""
    # try:
    # Validate inputs
    if not text or text is None:
        print("Error: Text is None or empty")
        return False
    
    text = str(text).strip()
    if not text:
        print("Error: Text is empty after stripping")
        return False
    
    # Initialize a client for the specified index
    pc_index = pc.Index(index)

    # Delete old chunks for this specific platform_user_id and provider_id
    # This ensures we only remove data from the same source before uploading new content
    index_stats = pc_index.describe_index_stats()
    if platform_user_id in index_stats.namespaces:
        print(f"Namespace '{platform_user_id}' found. Deleting old chunks for provider_id: {provider_id}...")
        # Delete vectors that match both platform_user_id (namespace) and provider_id (metadata filter)
        pc_index.delete(
            filter={
                "platform": {"$eq": platform},
                "provider_id": {"$eq": provider_id}
            },
            namespace=platform_user_id
        )
        print(f"Deleted old chunks for platform={platform}, provider_id={provider_id}")
    else:
        print(f"Namespace '{platform_user_id}' not found. A new one will be created upon upload.")


    # Split text into chunks
    chunks = split_text_into_chunks(text)
    print(f"Split text into {len(chunks)} chunks")

    # Prepare vectors for upload
    vectors = []
    for i, chunk in enumerate(chunks):
        # Generate embedding
        embedding = get_embedding(chunk)
        if not embedding:
            continue

        # Create metadata
        metadata = {
            "text": chunk,
            "platform": platform,
            "platform_user_id": platform_user_id,
            "provider_id": provider_id,
            "type": type,
            "chunk_id": i,
            "document_id": f"doc_{uuid.uuid4().hex[:8]}"
        }

        # Create vector object
        vector_obj = {
            "id": f"chunk_{uuid.uuid4().hex[:12]}",
            "values": embedding,
            "metadata": metadata
        }

        vectors.append(vector_obj)

    # Upload vectors in batches (Pinecone recommends batches of 100)
    batch_size = 100
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i:i + batch_size]
        pc_index.upsert(
            vectors=batch,
            namespace=platform_user_id
        )
        print(f"Uploaded batch {i//batch_size + 1}: {len(batch)} vectors")

    print(
        f"Successfully uploaded {len(vectors)} vectors to index '{index}'")
    return True

    # except Exception as e:
    #     print(f"Error uploading data: {e}")
    #     return False
