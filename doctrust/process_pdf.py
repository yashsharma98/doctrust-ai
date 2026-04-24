import logging

import chromadb
import fitz
from django.conf import settings

from .create_vectors import embedded_texts

logger = logging.getLogger(__name__)

chroma_db_client = None


# using cloud chroma db
def chroma_db():
    global chroma_db_client

    if not settings.CHROMA_API_KEY or not settings.CHROMA_TENANT or not settings.CHROMA_DATABASE:
        raise ValueError("Database configuration missing")

    if chroma_db_client is None:
        chroma_db_client = chromadb.CloudClient(api_key=settings.CHROMA_API_KEY, tenant=settings.CHROMA_TENANT, database=settings.CHROMA_DATABASE)
    return chroma_db_client


def pdf_name(doc_id):
    cleaned_name = str(doc_id).replace("-", "_")
    return cleaned_name


def save_pdf_to_db(doc_id, pdf_path, chunk_size=500, overlap=100):
    pdf_file = fitz.open(pdf_path)
    total_pages = len(pdf_file)

    all_extracted_chunks = []
    current_index = 0

    for page_num in range(total_pages):
        page_data = pdf_file[page_num]
        page_text = page_data.get_text("text").strip()

        # skip when pages are blank
        if page_text == "":
            continue

        # splitting the text into overlapping chunks (overlapping because it revents breaking meaning across chunks to improve the quality)
        page_chunks = text_split(page_text, chunk_size, overlap, page_num + 1, current_index)

        for c in page_chunks:
            all_extracted_chunks.append(c)

        # update index so next page continues with the numbering to prevent the restarting from new page
        current_index = current_index + len(page_chunks)

    pdf_file.close()

    if len(all_extracted_chunks) == 0:
        raise ValueError("Could not extract any text from PDF")

    # Embedding each chunks by converting into a vector for semantic search
    just_texts = []
    for chunk in all_extracted_chunks:
        just_texts.append(chunk["text"])

    vectors = embedded_texts(just_texts)

    # storing in chroma db for each document (separate collection)
    db = chroma_db()
    col_name = pdf_name(doc_id)
    my_collection = db.get_or_create_collection(name=col_name, metadata={"hnsw:space": "cosine"})

    # showing position of chunks
    id_list = []
    meta_list = []
    for chunk in all_extracted_chunks:
        id_list.append(f"{doc_id}_chunk_{chunk['chunk_index']}")
        meta_list.append({"page": chunk["page"], "chunk_index": chunk["chunk_index"]})

    my_collection.add(ids=id_list, embeddings=vectors, documents=just_texts, metadatas=meta_list)

    return total_pages, len(all_extracted_chunks)


def delete_pdf(doc_id):
    db = chroma_db()
    try:
        db.delete_collection(name=pdf_name(doc_id))
    except Exception as e:
        logger.warning(f"ChromaDB Delete Failed - doc_id={doc_id}, error={str(e)}")

        return False


# splits long text into overlapping chunks to preserve context so that they can be embedded and searched
def text_split(text, chunk_size, overlap, page, start_index):
    chunks = []
    start_pos = 0
    index = start_index

    while start_pos < len(text):
        end_pos = start_pos + chunk_size
        piece = text[start_pos:end_pos].strip()

        if piece != "":
            chunks.append({"text": piece, "page": page, "chunk_index": index})
            index = index + 1

        if end_pos >= len(text):
            break

        # overlapping the chunks from previous to preserve the context (continue with some parts of previous into next chunk)
        start_pos = start_pos + (chunk_size - overlap)

    return chunks
