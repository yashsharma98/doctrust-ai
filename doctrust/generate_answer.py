from django.conf import settings
from google import genai


def generate_answer(question, chunks):
    if not settings.GEMINI_API_KEY:
        return None

    try:
        context_text = ""
        chunk_num = 1

        for chunk in chunks:
            context_text += f"[Source {chunk_num} — Page {chunk['page']}]\n"
            context_text += f"{chunk['text']}\n\n"
            chunk_num += 1

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=f"""
                    You are a AI document assistant. Analyse the query and the chunks.

                    Query: {question}

                    Document excerpts:
                    {context_text}

                    Instructions:
                    Write a natural response for a non-technical user.
                    
                    Step 1: Evaluate the query complexity.
                    - Is it a simple question answered by the text? -> Use format A.
                    - Is it complex, or is the document missing info? -> Use format B.

                    Format A (Simple answer):
                    <div>
                        <p>[Write a clear answer based only on the text.]</p>
                    </div>

                    Format B (Nuanced answer):
                    <div>
                        <ul>
                            <li>[Natural statement about a detail found or a specific gap]</li>
                        </ul>
                        <p>[Write final synthesis here based only on text.]</p>
                    </div>

                    Rules:
                    - Output must be valid HTML only.
                    - Start immediately with <div>.
                    - Do not invent information.
                    """
        )

        return response.text.strip()

    except Exception:
        return None


# used during failure to explain missing info
def generate_failure_insight(question, chunks):
    if not settings.GEMINI_API_KEY:
        return None

    try:
        context_text = ""
        for chunk in chunks:
            conf_score = int(chunk["confidence"] * 100)
            context_text += f"[Page {chunk['page']} | Confidence: {conf_score}%]\n"
            context_text += f"{chunk['text']}\n\n"

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=f"""
                    You are a AI document assistant. The user asked a question, but our system determined the document does not contain enough info.

                    Query: {question}

                    Closest excerpts found:
                    {context_text}

                    Instructions:
                    Explain exactly what is missing from the excerpts that prevents a full answer.

                    Format exactly like this:
                    <div>
                    <p>We could not find a complete answer to your query in the document. Here is the breakdown of what is missing:</p>
                    <ul>
                        <li><strong>[Specific part missing]</strong>: [Explain what the document actually says, and what is missing]</li>
                    </ul>
                    </div>
                    """,
        )

        return response.text.strip()

    except Exception:
        return None
