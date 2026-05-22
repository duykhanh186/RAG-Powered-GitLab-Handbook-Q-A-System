import os
from qdrant_client import QdrantClient

def check():
    qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
    qdrant_key = os.getenv("QDRANT_API_KEY", None)
    client = QdrantClient(url=qdrant_url, api_key=qdrant_key)
    collection_name = "gitlab_handbook"
    
    if not client.collection_exists(collection_name):
        print(f"Collection {collection_name} does not exist!")
        return
        
    info = client.get_collection(collection_name)
    print(f"Points count: {info.points_count}")
    print(f"Status: {info.status}")
    
    # Scroll points to see metadata
    records, next_page = client.scroll(
        collection_name=collection_name,
        limit=100,
        with_payload=True,
        with_vectors=False
    )
    
    print("\n--- Sample Points Metadata & doc_id types ---")
    doc_ids = set()
    null_doc_ids = 0
    types = {}
    for r in records:
        payload = r.payload or {}
        metadata = payload.get("metadata", {})
        doc_id = metadata.get("doc_id")
        if doc_id is not None:
            doc_ids.add(doc_id)
            t = type(doc_id).__name__
            types[t] = types.get(t, 0) + 1
        else:
            null_doc_ids += 1
            
    print(f"Total points fetched: {len(records)}")
    print(f"Unique doc_ids found: {doc_ids}")
    print(f"Points with null/missing doc_id: {null_doc_ids}")
    print(f"doc_id types distribution: {types}")
    
    if records:
        print("\nFirst point payload sample:")
        print(records[0].payload)

if __name__ == "__main__":
    check()
