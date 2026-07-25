# AGENTS.md

## Project Overview

This workspace supports the MOD-SA ("มดซ่า") project: an intelligent KMUTT Student Affairs chatbot built with Large Language Models (LLMs) and Retrieval-Augmented Generation (RAG).

The chatbot should help current KMUTT students, prospective students, parents, and student-service staff quickly access trustworthy university information. Core information domains include academic regulations, registration, class schedules, academic calendars, scholarships, FAQs, and student services.

## Primary Goals

- Build a chatbot for KMUTT students, parents, and prospective applicants using LLMs with RAG.
- Prepare a reliable Knowledge Base for student-affairs and student-service information.
- Prefer answers grounded in curated institutional sources over model memory.
- Reduce hallucination by retrieving relevant source material before generating answers.
- Support 24-hour access to common service information and reduce repetitive staff workload.
- Keep the system extensible for future integration with university systems and personalized advisory features.

## Expected Technical Direction

- Use Python as the default implementation language unless the repository establishes another stack.
- Use a RAG framework such as LangChain or LlamaIndex when helpful.
- Use a vector database or vector index for retrieval.
- Store prepared knowledge data in structured formats suitable for ingestion, especially JSON with metadata.
- Build or integrate a web-based chat UI when the project reaches the application layer.
- LLMs may be open-source models or commercial APIs, depending on cost, accuracy, privacy, and deployment constraints.

## Knowledge Base Requirements

When adding or modifying data pipelines:

- Collect information from authoritative KMUTT/student-affairs sources only.
- Preserve source metadata, such as title, source URL or document name, department/owner, date, language, category, and last-updated date when available.
- Chunk text for retrieval with enough surrounding context to answer policy and procedure questions accurately.
- Avoid losing important Thai terminology, dates, conditions, exceptions, or eligibility rules during cleaning.
- Keep raw, processed, and indexed data separate when the project structure allows it.
- Design ingestion so documents can be refreshed as university policies, calendars, and service information change.

## Chatbot Behavior Requirements

- Answer in Thai by default when the user asks in Thai; answer in English when the user asks in English.
- Ground answers in retrieved project knowledge whenever possible.
- If the Knowledge Base does not contain enough evidence, say that the information is unavailable or needs confirmation instead of guessing.
- Include concise source references or citations when the UI or response format supports them.
- Be especially careful with dates, deadlines, registration windows, scholarship criteria, fees, academic rules, and eligibility conditions.
- Do not provide personalized academic, legal, medical, financial, or immigration advice beyond what is explicitly supported by retrieved official information.
- Escalate users to the relevant university office or staff contact when a question requires human judgment or private student records.

## Evaluation And Success Metrics

Changes should preserve or improve:

- Answer accuracy against verified source material.
- Retrieval relevance for common student-service questions.
- User satisfaction and clarity of responses.
- Coverage of frequent questions about registration, academic regulations, scholarships, academic calendars, and student services.
- Completeness of delivered system documentation.

When practical, add tests or evaluation scripts for:

- Retrieval quality on known FAQs.
- Citation/source matching.
- Thai-language answer quality.
- Failure behavior when no reliable source is found.
- Regression cases for high-risk university policy questions.

## Implementation Guidelines

- Keep implementations modular: ingestion, chunking, embedding, retrieval, generation, UI, and evaluation should be separable where practical.
- Prefer configuration files or environment variables for model names, API keys, database paths, chunk sizes, and deployment settings.
- Never commit secrets, API keys, tokens, private student data, or credentials.
- Treat student records and any personally identifiable information as sensitive. Do not use private data in prompts, logs, tests, or sample fixtures.
- Log enough diagnostic information to debug retrieval and generation, but avoid storing sensitive user content unnecessarily.
- Document setup, data ingestion, evaluation, and deployment steps as they are added.

## Project Phases From The Proposal

Use these phases as a guide when planning work:

1. Requirement analysis and system design.
2. Data collection and preparation.
3. Knowledge-base conversion, RAG development, and chatbot integration.
4. Model improvement and system testing.
5. Beta trial, fixes, final report, and handoff.

## Documentation Expectations

Maintain clear documentation for:

- System architecture and major dependencies.
- Knowledge sources and update process.
- Data schema and metadata fields.
- How to run ingestion, indexing, evaluation, and the chat application.
- Known limitations and cases that require staff confirmation.
- Budget-sensitive infrastructure decisions, including model/API token usage, GPU needs, cloud services, or local GPU alternatives such as RTX 4070-class hardware.

## Local Workspace Notes

- The current workspace initially contains the proposal PDF only: `MODsa-proposal_students.pdf`.
- If creating a new codebase, choose a simple, reproducible structure and include a README with setup instructions.
- Before making broad architectural changes, inspect the current files and follow any established patterns.
