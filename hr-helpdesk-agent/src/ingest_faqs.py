"""
Ingest HR FAQ documents into a dedicated Pinecone index.
Run this script once (and whenever FAQs are updated) to populate the vector store.

Usage:
    cd src
    python ingest_faqs.py

Environment variables required (see .env):
    PINECONE_API_KEY   - Pinecone API key
    PINECONE_FAQ_INDEX - Name of the Pinecone index for FAQs (e.g. "faqs")
"""
import os
from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec
from langchain_pinecone import PineconeVectorStore
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

FAQ_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "faqs")
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 400
CHUNK_OVERLAP = 50

# all-MiniLM-L6-v2 produces 384-dimensional vectors
EMBEDDING_DIMENSION = 384


def main():
    index_name = os.getenv("PINECONE_FAQ_INDEX")
    if not index_name:
        raise ValueError("PINECONE_FAQ_INDEX environment variable is not set.")

    print(f"Loading FAQ documents from: {FAQ_DATA_PATH}")

    loader = DirectoryLoader(
        FAQ_DATA_PATH,
        glob="**/*.txt",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
    )
    documents = loader.load()

    if not documents:
        print("No FAQ documents found. Add .txt files to the faqs/ directory and re-run.")
        return

    print(f"Loaded {len(documents)} document(s).")

    print("Splitting documents into chunks...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    docs = splitter.split_documents(documents)
    print(f"Chunks created: {len(docs)}")

    print("Loading embedding model...")
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

    print("Connecting to Pinecone...")
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

    existing_indexes = [idx.name for idx in pc.list_indexes()]
    if index_name not in existing_indexes:
        print(f"Index '{index_name}' not found. Creating it...")
        pc.create_index(
            name=index_name,
            dimension=EMBEDDING_DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        print(f"Index '{index_name}' created.")
    else:
        print(f"Index '{index_name}' already exists.")

    print(f"Uploading {len(docs)} chunks to Pinecone index '{index_name}'...")
    PineconeVectorStore.from_documents(
        docs,
        embedding=embeddings,
        index_name=index_name,
    )

    print("FAQ documents uploaded to Pinecone successfully.")


if __name__ == "__main__":
    main()
