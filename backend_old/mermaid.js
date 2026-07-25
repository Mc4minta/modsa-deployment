const ragProcessDiagram = String.raw`flowchart TD
  %% MOD-SA RAG process overview

  subgraph S[Knowledge Preparation]
    S1[Official KMUTT sources]
    S2[Source discovery\nknowledge/ + proposal PDF]
    S3[Fingerprint files\nSHA-256 + size + mtime]
    S4{Manifest changed?}
    S5[Load documents\nPDF, TXT, MD, JSON]
    S6[Split into chunks\nRecursiveCharacterTextSplitter]
    S7[Embed chunks]
    S8[Store in Chroma DB]
    S9[Save manifest]
  end

  subgraph Q[Question Answering]
    Q1[User asks a question]
    Q2[Check current index]
    Q3[Retrieve top-k chunks]
    Q4[Build context\nwith source labels]
    Q5[Create prompt\nThai or English]
    Q6[LLM generates answer]
    Q7[Return answer + sources]
  end

  subgraph A[Operational Triggers]
    A1[App startup]
    A2[POST /ask]
    A3[POST /reindex]
  end

  A1 --> S2
  A2 --> Q1
  A3 --> S2

  S2 --> S3 --> S4
  S4 -- no --> S5
  S4 -- yes --> S8
  S5 --> S6 --> S7 --> S8 --> S9

  Q1 --> Q2 --> Q3 --> Q4 --> Q5 --> Q6 --> Q7

  Q2 -. uses .-> S8
  Q3 -. pulls relevant chunks from .-> S8
  A2 -. refreshes if sources changed .-> S4

  Q6 --> R{Enough verified\ncontext?}
  R -- no --> R1[Say information is insufficient\nand recommend KMUTT office]
  R -- yes --> Q7
`;

function getMermaidDiagram() {
  return ragProcessDiagram;
}

module.exports = {
  ragProcessDiagram,
  getMermaidDiagram,
};

if (require.main === module) {
  process.stdout.write(ragProcessDiagram);
}
