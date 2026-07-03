from pathlib import Path

from src.pipeline import run


if __name__ == "__main__":
    run(Path(__file__).resolve().parent)
