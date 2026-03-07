"""
RAG (Retrieval-Augmented Generation) for HR FAQs.
Queries the dedicated Pinecone FAQ index to answer employee questions.
Requires PINECONE_FAQ_INDEX to be set in the environment and populated via ingest_faqs.py.
"""
import os
from dotenv import load_dotenv

from langchain_pinecone import PineconeVectorStore
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI

load_dotenv()

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-V3")
HF_BASE_URL = os.getenv("HF_BASE_URL", "https://router.huggingface.co/v1")

embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

vectorstore = PineconeVectorStore.from_existing_index(
    index_name=os.getenv("PINECONE_FAQ_INDEX"),
    embedding=embeddings,
)

llm = ChatOpenAI(
    model=LLM_MODEL,
    api_key=os.getenv("HF_TOKEN"),
    base_url=HF_BASE_URL,
    temperature=0,
)

retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

SYSTEM_PROMPT = """
You are a helpful HR assistant answering frequently asked employee questions using the company FAQ documents.

Rules:
- Only use the information provided in the context.
- If the answer is not in the context, say you don't have enough information and direct the employee to contact HR at hr@company.com or call (555) 123-4567.
- Keep answers concise, friendly, and actionable.
- Do not invent policies, numbers, or contact details.
"""


def query_faq(question: str) -> str:
    """
    Retrieve relevant FAQ chunks from Pinecone and generate an answer using the LLM.

    Args:
        question: The employee's question or topic.

    Returns:
        The LLM-generated answer as a string.
    """
    docs = retriever.invoke(question)
    context = "\n\n".join([d.page_content for d in docs])
    user_prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"Context:\n{context}\n\n"
        f"Question:\n{question}\n\n"
        f"Answer:"
    )
    response = llm.invoke(user_prompt)
    return response.content
