import os
import secrets


def run_setup():
    print("=" * 60)
    print("  SIGNAL CITY v2.0 - First-Time Setup Wizard")
    print("=" * 60)
    print()

    config = {}

    config["JWT_SECRET"] = secrets.token_urlsafe(32)
    print("[OK] JWT_SECRET auto-generated.")

    print()
    print("GROQ API KEY (Free NLP commands - get one at console.groq.com)")
    groq_key = input("  Groq API Key (press Enter to skip - regex fallback will be used): ").strip()
    config["GROQ_API_KEY"] = groq_key if groq_key else ""
    print("  [OK] Groq API key saved." if groq_key else "  [~] Skipped. NLP will use regex keyword matching.")

    print()
    print("MONGODB URI (optional - leave blank to use fast in-memory storage)")
    mongo_uri = input("  MongoDB URI (press Enter to skip): ").strip()
    config["MONGODB_URI"] = mongo_uri if mongo_uri else ""
    print("  [OK] MongoDB URI saved." if mongo_uri else "  [~] Skipped. Using in-memory database.")

    print()
    print("OPENWEATHERMAP API KEY (optional - leave blank for simulated weather)")
    owm_key = input("  OWM API Key (press Enter to skip): ").strip()
    config["OWM_API_KEY"] = owm_key if owm_key else ""
    print("  [OK] OpenWeatherMap key saved." if owm_key else "  [~] Skipped. Weather will be simulated.")

    os.makedirs("data/cities", exist_ok=True)
    os.makedirs("data/graphs", exist_ok=True)

    with open(".env", "w", encoding="utf-8") as f:
        for key, value in config.items():
            f.write(f"{key}={value}\n")

    print()
    print("=" * 60)
    print("  [OK] .env file written successfully.")
    print()
    print("  Next steps:")
    print("    1. pip install -r requirements.txt")
    print("    2. python server.py")
    print("    3. Open http://localhost:8000")
    print()
    print("  City graphs will be downloaded automatically on first load.")
    print("  This may take 30-60 seconds per city on first run.")
    print("=" * 60)


if __name__ == "__main__":
    run_setup()
