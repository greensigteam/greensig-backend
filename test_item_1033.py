import requests

# Test the specific item that's failing
url = "http://localhost:8000/api/arbres/1033/"

try:
    print(f"Testing: {url}")
    response = requests.get(url, timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print("\n✓ SUCCESS - Item found!")
        data = response.json()
        print(f"\nResponse structure:")
        print(f"  Keys: {list(data.keys())}")
        print(f"\nFull data:")
        import json
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(f"\n✗ ERROR - Status {response.status_code}")
        print(f"Response: {response.text}")
        
except Exception as e:
    print(f"\n✗ EXCEPTION: {type(e).__name__}: {e}")

# Also test with unified endpoint
print("\n" + "="*60)
print("Testing with unified endpoint...")
url2 = "http://localhost:8000/api/inventory/?id=1033"
try:
    print(f"Testing: {url2}")
    response = requests.get(url2, timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print("\n✓ SUCCESS!")
        data = response.json()
        print(f"Count: {data.get('count')}")
        print(f"Results: {len(data.get('results', []))} items")
        if data.get('results'):
            print(f"\nFirst result keys: {list(data['results'][0].keys())}")
    else:
        print(f"\n✗ ERROR - Status {response.status_code}")
        
except Exception as e:
    print(f"\n✗ EXCEPTION: {type(e).__name__}: {e}")
