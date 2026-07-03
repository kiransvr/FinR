"""
run_api.py — Start the Loan Default Risk API.

Usage:
    python run_api.py
    python run_api.py --port 8080
"""
import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Loan Default Risk")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--reload", action="store_true", help="Enable hot-reload (dev only)")
    args = parser.parse_args()

    print(f"\n🚀 Starting Loan Default Risk on http://{args.host}:{args.port}")
    print(f"   Docs:   http://localhost:{args.port}/docs")
    print(f"   Health: http://localhost:{args.port}/api/v1/health\n")

    uvicorn.run(
        "src.api.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
