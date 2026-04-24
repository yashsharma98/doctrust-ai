from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from .check_scores import evaluate
from .generate_answer import generate_answer, generate_failure_insight
from .models import Document, Question
from .process_pdf import delete_pdf, save_pdf_to_db
from .search_db import retrieve


def index(request):
    documents = Document.objects.all()
    return render(request, "doctrust/index.html", {"documents": documents})


def upload(request):
    if request.method == "POST":
        pdf_file = request.FILES.get("pdf_file")

        if not pdf_file:
            messages.error(request, "Select only PDF file")
            return redirect("index")
        if not pdf_file.name.lower().endswith(".pdf"):
            messages.error(request, "Only PDF files are accepted")
            return redirect("index")
        if pdf_file.size > 20 * 1024 * 1024:
            messages.error(request, "Select files less than 20mb")
            return redirect("index")

        doc = Document.objects.create(name=pdf_file.name, file=pdf_file)

        try:
            # processing the pdf & saving in chroma db
            page_count, chunk_count = save_pdf_to_db(str(doc.id), doc.file.path)

            doc.page_count = page_count
            doc.chunk_count = chunk_count
            doc.status = "ready"
            doc.save()

            return redirect("doc_detail", doc_id=doc.id)

        except Exception as e:
            doc.status = "failed"
            doc.error_msg = str(e)
            doc.save()
            messages.error(request, f"Failed to process document: {e}")
            return redirect("index")

    return redirect("index")


def doc_detail(request, doc_id):
    doc = get_object_or_404(Document, id=doc_id)

    result = None
    if request.method == "POST" and doc.status == "ready":
        question = request.POST.get("question", "").strip()

        if question:
            chunks = retrieve(str(doc.id), question)

            if chunks is None:
                chunks = []
            # checking scores
            val = evaluate(chunks)

            if not val["sufficient"]:
                # if it failed then generate explanation instead of hallucinating
                if len(val["top_chunks"]) > 0:
                    answer = generate_failure_insight(question, val["top_chunks"])
                    no_answer = False

                    if not answer:
                        no_answer = True
                        answer = "Unable to generate answer"
                else:
                    answer = val["failure_reason"]
                    no_answer = True
                is_sufficient = False
            else:
                # only generate answer if confidence is good
                answer = generate_answer(question, val["top_chunks"])
                no_answer = False

                if not answer:
                    no_answer = True
                    answer = "Unable to generate answer"
                is_sufficient = True

            session = Question.objects.create(
                document=doc,
                question=question,
                answer=answer,
                confidence=val["confidence"],
                is_sufficient=is_sufficient,
            )

            result = {
                "question": question,
                "answer": answer,
                "confidence": val["confidence"],
                "is_sufficient": is_sufficient,
                "no_answer": no_answer,
            }

    question = doc.questions.order_by("-created_at")[:20]

    return render(request, "doctrust/doc_detail.html", {"doc": doc, "result": result, "question": question})


def delete_doc_question(request, session_id):
    if request.method == "POST":
        session = get_object_or_404(Question, id=session_id)
        doc_id = session.document.id
        session.delete()
        return redirect("doc_detail", doc_id=doc_id)
    return redirect("index")


def delete_document(request, doc_id):
    if request.method == "POST":
        doc = get_object_or_404(Document, id=doc_id)

        # delete vector embeddings from db
        try:
            delete_pdf(str(doc.id))
        except Exception:
            messages.warning(request, "Document data could not be removed")

        # remove file from local storage
        try:
            if doc.file and doc.file.storage.exists(doc.file.name):
                doc.file.delete(save=False)
        except Exception:
            messages.warning(request, "File could not be deleted")

        # delete entire document
        try:
            doc.delete()
        except Exception:
            messages.error(request, "Could not delete document")
            return redirect("index")

    return redirect("index")
