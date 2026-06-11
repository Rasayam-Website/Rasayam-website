import os
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("⚠️  python-dotenv not installed. Relying on system environment variables.")


def run_diagnostic():
    has_errors = False
    print("=" * 60)
    print(" 🌟 RASAYAM PRODUCTION-READY DIAGNOSTIC CHECKER 🌟 ")
    print("=" * 60)

    # 1. Database connection string
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        print("❌ DB ERROR: 'DATABASE_URL' is missing.")
        has_errors = True
    else:
        print("✅ DB STATUS: Connection string present.")

    # 2. AWS S3 bucket access
    print("\n--- Testing AWS S3 Storage ---")
    bucket = os.getenv('AWS_STORAGE_BUCKET_NAME')
    if not bucket:
        print("⚠️  S3 SKIPPED: AWS_STORAGE_BUCKET_NAME not set.")
    else:
        try:
            import boto3
            from botocore.config import Config
            s3 = boto3.client(
                's3',
                region_name=os.getenv('AWS_S3_REGION_NAME') or os.getenv('AWS_DEFAULT_REGION'),
                config=Config(connect_timeout=5, read_timeout=5),
            )
            s3.head_bucket(Bucket=bucket)
            print(f"✅ S3 STATUS: Bucket '{bucket}' accessible.")
        except Exception as e:
            print(f"❌ S3 ERROR: {e}")
            has_errors = True

    # 3. Razorpay payment gateway
    print("\n--- Testing Razorpay Payment Gateway ---")
    try:
        import razorpay
        rz_id = os.getenv('RAZORPAY_KEY_ID')
        rz_secret = os.getenv('RAZORPAY_KEY_SECRET')
        if not rz_id or not rz_secret:
            raise ValueError("RAZORPAY_KEY_ID or RAZORPAY_KEY_SECRET missing.")
        razorpay.Client(auth=(rz_id, rz_secret)).order.all({"count": 1})
        print("✅ RAZORPAY STATUS: Gateway credentials authorised.")
    except Exception as e:
        print(f"❌ RAZORPAY ERROR: {e}")
        has_errors = True

    print("=" * 60)
    if has_errors:
        sys.exit(1)


if __name__ == "__main__":
    run_diagnostic()
