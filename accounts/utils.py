import requests
from io import BytesIO
from django.conf import settings

def verify_face(stored_image_url, uploaded_image_file):
    # Face++ Compare Endpoint
    url = "https://api-cn.faceplusplus.com/facepp/v3/compare"
    
    try:
        # 1. Get the Master Image from Cloudinary
        resp = requests.get(stored_image_url, timeout=10)
        if resp.status_code != 200:
            print("Failed to download master image from Cloudinary")
            return False
        
        # 2. Prepare the Login Image (The one from your HP EliteBook)
        uploaded_image_file.seek(0)
        login_bytes = uploaded_image_file.read()

        # 3. Data payload (API Credentials)
        data = {
            'api_key': settings.FACE_API_KEY,
            'api_secret': settings.FACE_API_SECRET,
        }

        # 4. Files payload (The actual images)
        # Face++ is picky: use 'image_file1' and 'image_file2'
        files = {
            'image_file1': ('master.jpg', BytesIO(resp.content), 'image/jpeg'),
            'image_file2': ('login.jpg', BytesIO(login_bytes), 'image/jpeg')
        }

        # 5. Execute Request
        response = requests.post(url, data=data, files=files, timeout=30)
        result = response.json()

        # --- TERMINAL LOGS ---
        if 'error_message' in result:
            print(f"Face++ Error: {result['error_message']}")
            return False

        confidence = result.get('confidence', 0)
        print(f"--- BIOMETRIC RESULT: {confidence}% ---")

        # Threshold: 75 is standard, 60 is "Demo Friendly"
        return confidence > 70.0

    except Exception as e:
        print(f"Face API Logic Error: {e}")
        return False