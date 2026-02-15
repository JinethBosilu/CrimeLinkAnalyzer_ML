import requests
import json

files = {'image': ('0_Ranil.jpg', open('stored_images/criminal_4/0_Ranil.jpg', 'rb'), 'image/jpeg')}
data = {'threshold': '45'}
r = requests.post('http://localhost:5002/analyze', files=files, data=data)

print(f"Status code: {r.status_code}")

result = r.json()

# Write full response to file for inspection
with open('api_response.json', 'w') as f:
    json.dump(result, f, indent=2)
    
print("Response written to api_response.json")
print(f"found_matches: {result.get('found_matches')}")
print(f"match_count: {result.get('match_count')}")

if result.get('matches'):
    for m in result['matches']:
        print(f"\nMatch: {m.get('name')}")
        print(f"  NIC: {m.get('nic')}")
        print(f"  similarity: {m.get('similarity')}")
        print(f"  risk_level: {m.get('risk_level')}")
        ch = m.get('crime_history')
        print(f"  crime_history: {ch}")
        if ch:
            print(f"    total_crimes: {ch.get('total_crimes')}")
            print(f"    crime_types: {ch.get('crime_types')}")
