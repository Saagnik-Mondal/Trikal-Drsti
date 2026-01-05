import requests
import time
import os

BASE_URL = "http://127.0.0.1:8000"

def test_api():
    print("Wait for server startup... (run 'python server.py' in another terminal first!)")
    # In this agent env, we might not be able to run background easily. 
    # But we can try to assume it's running or fail gracefully.
    
    # 1. Test MP4 Stub
    print("\n--- Testing MP4 Stub ---")
    with open("dummy.mp4", "wb") as f: f.write(b"fake video content")
    
    files = {'file': ('test.mp4', open('dummy.mp4', 'rb'), 'video/mp4')}
    try:
        r = requests.post(f"{BASE_URL}/upload", files=files)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.json()}")
        if r.status_code == 200 and r.json()['is_video']:
            print("✅ MP4 Stub verified.")
        else:
            print("❌ MP4 Stub failed.")
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        
    os.remove("dummy.mp4")

    # 2. Test CSV Upload
    print("\n--- Testing CSV Analysis ---")
    with open("test.csv", "w") as f:
        f.write("timestamp,value\n")
        f.write("2025-01-01 10:00,10.0\n")
        f.write("2025-01-01 11:00,12.0\n")
        f.write("2025-01-01 12:00,50.0\n") # Spike
    
    files = {'file': ('test.csv', open('test.csv', 'rb'), 'text/csv')}
    file_id = None
    try:
        r = requests.post(f"{BASE_URL}/upload", files=files)
        print(f"Upload Resp: {r.json()}")
        file_id = r.json()['id']
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return

    # 3. Poll Analysis
    if file_id:
        print(f"Polling ID: {file_id}")
        for _ in range(5):
            time.sleep(1)
            r = requests.get(f"{BASE_URL}/analysis/{file_id}")
            status = r.json().get('status')
            progress = r.json().get('progress')
            print(f"Status: {status} ({progress}%)")
            if status == 'completed':
                print("✅ Analysis Completed!")
                print("Timeline Sample:", r.json()['timeline'][0])
                break
        else:
            print("❌ Timeout waiting for analysis.")
            
    os.remove("test.csv")

if __name__ == "__main__":
    test_api()
