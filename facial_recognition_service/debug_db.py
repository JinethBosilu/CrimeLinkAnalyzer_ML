from utils.database import get_database

db = get_database()
embeddings = db.get_all_embeddings()

print(f"Found {len(embeddings)} criminals with embeddings")
for e in embeddings:
    print(f"\n{e['name']}:")
    print(f"  criminal_id: {e.get('criminal_id')}")
    print(f"  nic: {e.get('nic')}")
    print(f"  risk_level: {e.get('risk_level')}")
    print(f"  crime_history: {e.get('crime_history')}")
    print(f"  crime_history type: {type(e.get('crime_history'))}")
