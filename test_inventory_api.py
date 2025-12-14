import requests
import json

# Test the inventory endpoint
url = "http://localhost:8000/api/inventory/"
params = {
    "page": 1,
    "page_size": 20,
    "type": "Arbre,Palmier,Gazon,Arbuste,Vivace,Cactus,Graminee,Puit,Pompe,Vanne,Clapet,Canalisation,Aspersion,Goutte,Ballon"
}

try:
    print(f"Testing: {url}")
    print(f"Params: {params}")
    response = requests.get(url, params=params, timeout=10)
    print(f"\nStatus Code: {response.status_code}")
    print(f"\nResponse Headers:")
    for key, value in response.headers.items():
        print(f"  {key}: {value}")
    
    if response.status_code == 200:
        print("\n✓ SUCCESS - API is working!")
        data = response.json()
        print(f"\nCount: {data.get('count', 'N/A')}")
        print(f"Results: {len(data.get('results', []))} items")
    else:
        print(f"\n✗ ERROR - Status {response.status_code}")
        print(f"\nResponse body:")
        print(response.text)
        
except Exception as e:
    print(f"\n✗ EXCEPTION:")
    print(f"  {type(e).__name__}: {e}")
