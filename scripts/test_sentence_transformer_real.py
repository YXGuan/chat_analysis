import sys
import platform
import asyncio
from kura.embedding import SentenceTransformerEmbeddingModel


def main():
    if platform.system() != "Darwin":
        print("Skipping: This test only runs on macOS (Darwin).")
        sys.exit(0)

    texts = [
        "Hello world!",
        "Sentence Transformers are great.",
        "This is a test sentence.",
    ]

    async def run():
        print("Instantiating SentenceTransformerEmbeddingModel...")
        model = SentenceTransformerEmbeddingModel()
        print("Embedding texts:", texts)
        try:
            embeddings = await model.embed(texts)
            print("Embeddings:")
            for i, emb in enumerate(embeddings):
                print(f"Text {i}: {emb[:5]}... (len={len(emb)})")
        except Exception as e:
            print(f"Error during embedding: {e}")

    asyncio.run(run())


if __name__ == "__main__":
    main()
