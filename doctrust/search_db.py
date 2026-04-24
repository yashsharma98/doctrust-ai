import re

from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder

from .create_vectors import embedded_query
from .process_pdf import chroma_db, pdf_name

rerank_model = None

def reranking_model():
    global rerank_model
    if rerank_model is None:
        rerank_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return rerank_model


def split_into_words(text):
    return re.findall(r"\w+", text.lower())


def retrieve(doc_id, question):
    try:
        db = chroma_db()

        # get collection for the current document from chroma db
        my_collection = db.get_collection(name=pdf_name(doc_id))

        total_count = my_collection.count()

        # if chunks is zero then no searching is performed
        if total_count == 0:
            return []

        db_data = my_collection.get(include=["documents", "metadatas"])
        id_list = db_data["ids"]
        text_list = db_data["documents"]
        meta_list = db_data["metadatas"]

        id_to_text_map = {}
        id_to_meta_map = {}
        for i in range(len(id_list)):
            id_to_text_map[id_list[i]] = text_list[i]
            id_to_meta_map[id_list[i]] = meta_list[i]

        # semantic search using embeddings using cosine
        q_vector = embedded_query(question)
        limit = min(30, total_count)
        if total_count < 50:
            limit = total_count

        # finds closest chunks in meaning using cosine similarity
        vector_results = my_collection.query(
            query_embeddings=[q_vector],
            n_results=limit,
        )

        found_id_list = vector_results["ids"][0]

        # storing rank position. The lower the rank the better the similarities
        cosine_ranks = {}
        current_rank = 1
        for chunk_id in found_id_list:
            cosine_ranks[chunk_id] = current_rank
            current_rank += 1

        # using BM25 to perform keyword search for exact word matching
        word_chunks = []
        for text in text_list:
            word_chunks.append(split_into_words(text))

        bm25_searcher = BM25Okapi(word_chunks)
        q_words = split_into_words(question)
        keyword_scores = bm25_searcher.get_scores(q_words)

        # sort keyword scores
        score_index_pairs = []
        for i in range(len(keyword_scores)):
            score_index_pairs.append({"index": i, "score": keyword_scores[i]})

        score_index_pairs.sort(key=lambda x: x["score"], reverse=True)

        bm25_ranks = {}
        current_rank = 1
        for pair in score_index_pairs:
            real_id = id_list[pair["index"]]
            bm25_ranks[real_id] = current_rank
            current_rank += 1

        # combine all scores
        combined_scores = []
        for chunk_id in id_list:
            c_rank = cosine_ranks.get(chunk_id, total_count)
            b_rank = bm25_ranks.get(chunk_id, total_count)

            # semantic search + keyword search
            final_score = (1 / (c_rank + 60)) + (1 / (b_rank + 60))
            combined_scores.append({"id": chunk_id, "score": final_score})

        combined_scores.sort(key=lambda x: x["score"], reverse=True)

        # reducing the search upto 10
        top_10 = combined_scores[0:10]

        pairs_to_check = []
        for item in top_10:
            chunk_text = id_to_text_map[item["id"]]
            pairs_to_check.append((question, chunk_text))

        # final reranking using cross encoder to read both query and chunks together
        model = reranking_model()
        rerank_results = model.predict(pairs_to_check)

        final_list = []
        for i in range(len(top_10)):
            final_list.append({"id": top_10[i]["id"], "rerank_score": float(rerank_results[i])})

        final_list.sort(key=lambda x: x["rerank_score"], reverse=True)
        top_3 = final_list[0:3]

        final_output = []
        for item in top_3:
            chunk_id = item["id"]
            text = id_to_text_map[chunk_id]
            meta = id_to_meta_map[chunk_id]
            r_score = item["rerank_score"]

            # convert rerank score into sigmoid probability (0 to 1 range)
            math = 2.718**-r_score
            conf = 1 / (1 + math)

            final_output.append({"text": text, "page": meta.get("page", 0), "confidence": round(conf, 4)})

        return final_output
    
    except Exception:
        return None
