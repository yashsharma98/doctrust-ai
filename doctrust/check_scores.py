def evaluate(chunks):
    threshold = 0.40 # minimum confidence for chunk to be useful

    # if no chunks is zero then it fails
    if len(chunks) == 0:
        return {
            "sufficient": False,
            "confidence": 0.0,
            "top_chunks": [],
            "reason": "No chunks found",
            "failure_reason": "Database connection error. Please try again later.",
        }

    # find the highest score from all chunks
    high_confidence = 0.0
    for chunk in chunks:
        if chunk["confidence"] > high_confidence:
            high_confidence = chunk["confidence"]

    # find chunks that are above threshold
    passed_chunks = []
    for chunk in chunks:
        if chunk["confidence"] >= threshold:
            passed_chunks.append(chunk)

    # if no chunks passed then explain
    if len(passed_chunks) == 0:
        sorted_chunks = sorted(chunks, key=lambda x: x["confidence"], reverse=True) # sort highest first
        best_fails = sorted_chunks[0:3]

        # use best chunk to explain fail reason to user
        best_one = sorted_chunks[0]
        best_text = best_one["text"][0:120]
        best_page = best_one["page"]

        score_pct = int(best_one["confidence"] * 100)
        req_pct = int(threshold * 100)

        user_msg = (
            f"Insufficient information. "
            f"Your query needs {req_pct}% confidence, but best match was {score_pct}%.\n\n"
            f"Closest match found on Page {best_page}:\n"
            f'"{best_text}..."\n\n'
            f"Try rephrasing your question."
        )

        return {
            "sufficient": False,
            "confidence": round(high_confidence, 4),
            "top_chunks": best_fails,
            "reason": "Chunks below threshold",
            "failure_reason": user_msg,
        }

    return {
        "sufficient": True,
        "confidence": round(high_confidence, 4),
        "top_chunks": passed_chunks,
        "reason": "Passed guardrails",
        "failure_reason": "",
    }
