import os
from dotenv import load_dotenv
from pinecone import Pinecone
from langchain_pinecone import PineconeVectorStore
from langchain_community.document_loaders import DirectoryLoader, PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

load_dotenv()

DATA_PATH = "policies/"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

print("Loading documents...")

loader = DirectoryLoader(
    DATA_PATH,
    glob="**/*.pdf",
    loader_cls=PyMuPDFLoader
)

documents = loader.load() 

print("Splitting documents...")

splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP
)

docs = splitter.split_documents(documents)

print("Chunks created:", len(docs))

embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

print("Connecting to Pinecone...")

pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))

vectorstore = PineconeVectorStore.from_documents(
    docs,
    embedding=embeddings,
    index_name=os.getenv("PINECONE_INDEX")
)

print("Documents uploaded to Pinecone successfully.")