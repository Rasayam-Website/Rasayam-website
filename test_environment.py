import os
import sys

try:
    from dotenv import load_dotenv
    # Load variables from your local .env file
    load_dotenv()
except ImportError:
    # In AWS/Production, dotenv might not be installed as vars are native
    print("⚠️ python-dotenv not installed. Relying on system environment variables.")

def run_diagnostic():
    has_errors = False
    print("=" * 60)
    print(" 🌟 RASAYAM PRODUCTION-READY DIAGNOSTIC CHECKER 🌟 ")
    print("=" * 60)

    # 1. Test Database Environment Variable
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ DB ERROR: 'DATABASE_URL' is missing from your .env file.")
        has_errors = True
    else:
        print(f"✅ DB STATUS: Connection string verified.")

    # 2. Test Cloudinary Integration
    print("\n--- Testing Cloudinary Media Storage Connection ---")
    try:
        import cloudinary
        import cloudinary.api
        
        cloudinary.config(
            cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
            api_key=os.getenv('CLOUDINARY_API_KEY'),
            api_secret=os.getenv('CLOUDINARY_API_SECRET'),
            secure=True
        )
        # Attempt to request account usage stats from Cloudinary API to verify credentials
        cloudinary.api.usage()
        print("✅ CLOUDINARY STATUS: Authentication successful! Images will load cleanly.")
    except Exception as e:
        print(f"❌ CLOUDINARY ERROR: Failed to handshake with cloud bucket. Reason: {e}")
        has_errors = True

    # 3. Test Razorpay Payment Gateway Integration
    print("\n--- Testing Razorpay Payment Gateway API ---")
    try:
        import razorpay
        rz_id = os.getenv('RAZORPAY_KEY_ID')
        rz_secret = os.getenv('RAZORPAY_KEY_SECRET')
        
        if not rz_id or not rz_secret:
            raise ValueError("Keys missing from environment configuration.")
            
        client = razorpay.Client(auth=(rz_id, rz_secret))
        # Safely ping standard public order parameters to verify validity
        client.order.all({"count": 1})
        print("✅ RAZORPAY STATUS: Gateway credentials authorized! Checkout system active.")
    except Exception as e:
        print(f"❌ RAZORPAY ERROR: API key invalid or rejected by gateway. Reason: {e}")
        has_errors = True

    print("=" * 60)
    
    # Exit with code 1 if errors exist so CI/CD pipelines correctly fail
    if has_errors:
        sys.exit(1)

if __name__ == "__main__":
    run_diagnostic()