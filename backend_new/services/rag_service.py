from langchain_core.messages import (
    SystemMessage,
    HumanMessage
)

from core.llm import build_llm
from core.vectorstore import get_vector_store

from prompts.rag_prompt import SYSTEM_PROMPT



NO_VERIFIED_INFO_TH = (
    "ขออภัยครับ/ค่ะ ตอนนี้ผมยังไม่พบข้อมูลยืนยันจากฐานความรู้ที่เกี่ยวข้องกับคำถามนี้ "
    "แนะนำให้ตรวจสอบกับหน่วยงานของ KMUTT ที่เกี่ยวข้องโดยตรง"
)


NO_VERIFIED_INFO_EN = (
    "Sorry, I do not have enough verified information in the knowledge base to answer this confidently. "
    "Please confirm with the relevant KMUTT office."
)



def is_thai_text(text: str):

    return any(
        "\u0E00" <= char <= "\u0E7F"
        for char in text
    )



def no_verified_info_response(question):

    if is_thai_text(question):
        return NO_VERIFIED_INFO_TH

    return NO_VERIFIED_INFO_EN



def retrieve_documents(settings, question):

    vector_store = get_vector_store(settings)

    if hasattr(vector_store, "similarity_search"):
        return vector_store.similarity_search(
            question,
            k=settings.retrieval_k,
        )

    retriever = vector_store.as_retriever(
        search_kwargs={"k": settings.retrieval_k},
    )
    return retriever.invoke(question)



def format_context(docs):

    parts = []

    for index, doc in enumerate(docs, start=1):

        meta = doc.metadata

        label = (
            meta.get("title")
            or meta.get("source", "unknown source")
        )

        page = meta.get("page")

        if page is not None:
            label = (
                f"{label}, page {int(page)+1}"
            )


        parts.append(
            f"[{index}] {label}\n{doc.page_content}"
        )


    return "\n\n".join(parts)



def compute_confidence(docs):
    """Derive confidence level from retrieval quality."""
    count = len(docs) if docs else 0
    if count >= 3:
        return "high"
    if count == 2:
        return "medium"
    return "low"



def source_summary(docs):

    seen = set()
    sources = []


    for doc in docs:

        meta = doc.metadata

        source = meta.get(
            "source",
            "unknown"
        )

        page = meta.get("page")

        key = (
            source,
            page
        )


        if key in seen:
            continue


        seen.add(key)


        item = {
            "source": source
        }


        if meta.get("title"):
            item["title"] = meta["title"]


        if meta.get("department"):
            item["department"] = meta["department"]


        if meta.get("source_url"):
            item["url"] = meta["source_url"]


        if page is not None:
            item["page"] = int(page)+1


        sources.append(item)


    return sources



def answer_question(settings, question):


    docs = retrieve_documents(
        settings,
        question
    )


    if not docs:

        return {
            "answer": no_verified_info_response(question),
            "sources": [],
            "confidence": "low"
        }



    context = format_context(docs)


    prompt = SYSTEM_PROMPT.format(
        context=context
    )


    llm = build_llm(settings)



    response = llm.invoke(
        [
            SystemMessage(
                content=prompt
            ),
            HumanMessage(
                content=question
            )
        ]
    )


    return {
        "answer": response.content,
        "sources": source_summary(docs),
        "confidence": compute_confidence(docs)
    }