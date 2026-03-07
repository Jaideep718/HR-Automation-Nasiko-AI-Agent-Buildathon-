import os
from dotenv import load_dotenv

from langchain_pinecone import PineconeVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI

load_dotenv()

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
LLM_MODEL = "deepseek-ai/DeepSeek-V3"
HF_BASE_URL = "https://router.huggingface.co/v1"

embeddings = HuggingFaceEmbeddings(
    model_name=EMBEDDING_MODEL
)

vectorstore = PineconeVectorStore.from_existing_index(
    index_name=os.getenv("PINECONE_INDEX"),
    embedding=embeddings
)

llm = ChatOpenAI(
    model=LLM_MODEL,
    api_key=os.getenv("HF_TOKEN"),
    base_url=HF_BASE_URL,
    temperature=0
)

retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

SYSTEM_PROMPT = """
You are an HR assistant answering questions using company policy documents.

Rules:
- Only use the information in the context.
- If the answer is not in the context, say you don't have enough information.
- Do not invent HR policies.
"""

def query_policy(question: str):
    docs = retriever.invoke(question)
    context = "\n\n".join([d.page_content for d in docs])
    user_prompt = f"{SYSTEM_PROMPT}\n\nContext:\n{context}\n\nQuestion:\n{question}\n\nAnswer:"
    response = llm.invoke(user_prompt)
    return response.content