import math
from ..core.providers import rerank

class ContextRetriever:
    def __init__(self, provider):
        self.provider = provider

    def ingest(self, source):
        chunks = []
        for start in range(0, len(source["text"]), 1800):
            text = source["text"][start:start + 2000]
            chunks.append({"text": text, "offset": start, "embedding": self.provider.embed(text, "RETRIEVAL_DOCUMENT")})
        return {**source, "chunks": chunks, "embedding_model": self.provider.embedding_model}


    def retrieve(self, brand, query):
        vector = self.provider.embed(query[:8000], "RETRIEVAL_QUERY")
        norm = math.sqrt(sum(v * v for v in vector))
        ranked = []
        for source in brand["sources"]:
            if source["source_type"] == "previous_campaign":
                continue
            indexed = source if source.get("embedding_model") == self.provider.embedding_model and source.get("chunks") else self.ingest(source)
            for chunk in indexed["chunks"]:
                embedding = chunk["embedding"]
                score = sum(a * b for a, b in zip(vector, embedding)) / (norm * math.sqrt(sum(v * v for v in embedding)))
                ranked.append((score, {"id": source["id"], "name": source["name"], "text": chunk["text"], "offset": chunk["offset"]}))
        return rerank(query, [item for _, item in sorted(ranked, key=lambda pair: pair[0], reverse=True)[:8]])

