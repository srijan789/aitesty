import os
from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    debug = os.environ.get("FLASK_DEBUG", "True").lower() in ("true", "1", "t")
    print(f"\n🚀 Starting Aitesty Autonomous Test Orchestrator on http://127.0.0.1:{port}")
    print(f"📁 Workspaces root: {app.config['WORKSPACES_ROOT']}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
