import os

# TrueFoundry Gateway Configuration
os.environ.setdefault(
    "TRUEFOUNDRY_API_KEY",
    "tfy_pat_default-u3n8eaqjipdolz2w8cz3uhcm_0E2iyumk9OfB7Vo68461d1270ac232560fa7cdd084688708",
)
os.environ.setdefault("TRUEFOUNDRY_BASE_URL", "https://gateway.truefoundry.ai")
os.environ.setdefault("EXPLORER_MODEL", "openrouter/google-gemini-3.7-flash")

from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    debug = os.environ.get("FLASK_DEBUG", "True").lower() in ("true", "1", "t")
    print(f"\n🚀 Starting Aitesty Autonomous Test Orchestrator on http://127.0.0.1:{port}")
    print(f"📁 Workspaces root: {app.config['WORKSPACES_ROOT']}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
