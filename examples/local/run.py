"""Run the full Kura pipeline on a set of chats and open an HTML report of the results.

Usage (from the repo root, with the virtual environment active):

    python examples/local/run.py                         # 190 synthetic chats
    python examples/local/run.py --dataset wildchat      # every chat from 3 real English users
    python examples/local/run.py --dataset wildchat --users 2 --seed 7

Results are saved to examples/local/output/<sample>/<model>/. Running again
reuses them, so delete that folder to start over.
"""

import argparse
import asyncio
import json
import os
import re
import sys
import warnings
import webbrowser
from pathlib import Path
from typing import Any

from rich.console import Console

from kura.codex import DEFAULT_ENGINE, DEFAULT_MODEL
from kura.analysis import analyze_chats
from kura.types import Conversation

from report import write_report

SYNTHETIC_DATASET = "ivanleomk/synthetic-gemini-conversations"
OUTPUT_DIR = Path(__file__).parent / "output"
CACHE_DIR = OUTPUT_DIR / ".cache"
CLUSTER_FILES = ("clusters.jsonl", "meta_clusters.jsonl", "dimensionality.jsonl")

# scikit-learn's math on macOS prints many harmless matmul warnings during clustering.
warnings.filterwarnings("ignore", category=RuntimeWarning, module="sklearn")
warnings.filterwarnings("ignore", category=FutureWarning, module="sklearn")


def load_conversations(
    args: argparse.Namespace, output_dir: Path
) -> list[Conversation]:
    """Load the chats for this run, reusing the saved copy if there is one.

    The copy is also what the report reads, since the pipeline doesn't save it.
    """
    saved = output_dir / "conversations.jsonl"
    if saved.exists():
        with open(saved) as f:
            conversations = [Conversation.model_validate_json(line) for line in f]
        print(f"Reusing {len(conversations)} saved conversations from {saved}")
        return conversations

    if args.dataset == "wildchat":
        from wildchat import load_wildchat_users

        conversations = load_wildchat_users(
            args.users,
            args.language,
            args.seed,
            CACHE_DIR,
            topic=args.topic,
            model=args.model,
        )
    else:
        conversations = Conversation.from_hf_dataset(SYNTHETIC_DATASET, split="train")

    with open(saved, "w") as f:
        for conversation in conversations:
            f.write(conversation.model_dump_json() + "\n")
    return conversations


def reset_if_settings_changed(output_dir: Path, settings: dict[str, Any]) -> None:
    """Delete saved clustering results made with different settings, so they get redone.

    Summaries don't depend on these settings, so they are kept.
    """
    path = output_dir / "settings.json"
    if path.exists() and json.loads(path.read_text()) == settings:
        return
    stale = [
        output_dir / name for name in CLUSTER_FILES if (output_dir / name).exists()
    ]
    if stale:
        print("Clustering settings changed, so the clustering steps will run again.")
        for file in stale:
            file.unlink()
    path.write_text(json.dumps(settings, indent=2))


async def run_pipeline(
    conversations: list[Conversation], args: argparse.Namespace, output_dir: Path
) -> None:
    """Summarise, cluster, group, and project the chats, saving each step."""
    from kura.cache import DiskCacheStrategy
    from kura.checkpoints import JSONLCheckpointManager
    from kura.cluster import (
        ClusterDescriptionModel,
        KmeansClusteringModel,
        generate_base_clusters_from_conversation_summaries,
    )
    from kura.dimensionality import HDBUMAP, reduce_dimensionality_from_clusters
    from kura.meta_cluster import MetaClusterModel, reduce_clusters_from_base_clusters
    from kura.summarisation import SummaryModel, summarise_conversations
    from kura.visualization import visualise_pipeline_results

    model = f"openai/{args.model}"
    console = Console()

    summary_model = SummaryModel(
        model=model,
        console=console,
        cache=DiskCacheStrategy(cache_dir=str(OUTPUT_DIR / ".summary_cache")),
    )
    cluster_model = ClusterDescriptionModel(model=model, console=console)
    meta_cluster_model = MetaClusterModel(
        model=model, max_clusters=args.top_clusters, console=console
    )
    checkpoint_manager = JSONLCheckpointManager(str(output_dir), enabled=True)

    summaries = await summarise_conversations(
        conversations, model=summary_model, checkpoint_manager=checkpoint_manager
    )
    # This step takes clustering_model=, not model=. Passing model= is silently
    # ignored and Kura falls back to its default model.
    clusters = await generate_base_clusters_from_conversation_summaries(
        summaries,
        clustering_method=KmeansClusteringModel(clusters_per_group=args.cluster_size),
        clustering_model=cluster_model,
        checkpoint_manager=checkpoint_manager,
    )
    reduced_clusters = await reduce_clusters_from_base_clusters(
        clusters, model=meta_cluster_model, checkpoint_manager=checkpoint_manager
    )
    projected_clusters = await reduce_dimensionality_from_clusters(
        reduced_clusters,
        model=HDBUMAP(),
        checkpoint_manager=checkpoint_manager,
    )

    visualise_pipeline_results(projected_clusters, style="basic")


def main() -> None:
    """Parse options, run the pipeline, and open the report."""
    # Show progress right away, even when the output goes to a file
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--model", default=DEFAULT_MODEL, help="Model ID (default: GPT-6 Luna)"
    )
    parser.add_argument(
        "--engine",
        choices=["codex", "api"],
        default=DEFAULT_ENGINE,
        help="Headless Codex by default; API calls require an explicit opt-in",
    )
    parser.add_argument(
        "--dataset",
        choices=["synthetic", "wildchat"],
        default="synthetic",
        help="synthetic: 190 made-up chats. wildchat: every chat from a few real users",
    )
    parser.add_argument(
        "--users",
        type=int,
        choices=[1, 2, 3],
        default=3,
        help="WildChat only: how many users",
    )
    parser.add_argument(
        "--language",
        default="English",
        help="WildChat only: the language the users chat in",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="WildChat only: change to pick different users",
    )
    parser.add_argument(
        "--topic",
        help='WildChat only: pick users who chat about this, such as "science or physics research"',
    )
    parser.add_argument(
        "--cluster-size",
        type=int,
        default=5,
        help="about how many chats go in each base cluster (smaller makes more levels)",
    )
    parser.add_argument(
        "--top-clusters",
        type=int,
        default=5,
        help="keep grouping until at most this many top-level groups are left",
    )
    parser.add_argument(
        "--no-open", action="store_true", help="don't open the report in a browser"
    )
    args = parser.parse_args()

    if args.engine == "api" and not os.environ.get("OPENAI_API_KEY"):
        sys.exit("Set OPENAI_API_KEY first, for example: export OPENAI_API_KEY=sk-...")

    sample_name = args.dataset
    if args.dataset == "wildchat":
        sample_name = f"wildchat-{args.users}-{args.language.lower()}-users"
        if args.topic:
            sample_name += (
                "-about-"
                + re.sub(r"[^a-z0-9]+", "-", args.topic.lower()).strip("-")[:48]
            )
        elif args.seed != 42:
            sample_name += f"-seed{args.seed}"
    output_dir = (OUTPUT_DIR / sample_name / args.model).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.engine == "codex" and args.topic:
        sys.exit(
            "Topic-based WildChat sampling currently uses the legacy API pipeline. Choose --engine api explicitly, or omit --topic for headless Codex."
        )
    conversations = load_conversations(args, output_dir)
    if args.engine == "codex":
        chats = [conversation.model_dump(mode="json") for conversation in conversations]
        for chat in chats:
            chat["metadata"].setdefault("user", "User 1")
        profile_path = output_dir / "profile.json"
        profile = analyze_chats(
            chats,
            profile_path,
            output_dir / "codex-analysis",
            model=args.model,
            progress=lambda _stage, message: print(message, flush=True),
        )
        with (output_dir / "summaries.jsonl").open("w") as summaries:
            for chat in profile["chats"].values():
                summaries.write(
                    json.dumps({"chat_id": chat["chat_id"], "summary": chat["summary"]})
                    + "\n"
                )
        with (output_dir / "dimensionality.jsonl").open("w") as clusters:
            for topic in profile["clusters"]:
                clusters.write(
                    json.dumps(
                        {
                            **topic,
                            "level": topic["level"] - 1,
                            "chat_ids": topic["chats"],
                            "x_coord": topic.get("x", 0),
                            "y_coord": topic.get("y", 0),
                        }
                    )
                    + "\n"
                )
        report = write_report(output_dir, CACHE_DIR)
        print(f"Results: {profile_path}\nReport: {report}")
        if not args.no_open:
            webbrowser.open(report.as_uri())
        return
    reset_if_settings_changed(
        output_dir,
        {"cluster_size": args.cluster_size, "top_clusters": args.top_clusters},
    )
    asyncio.run(run_pipeline(conversations, args, output_dir))

    report = write_report(output_dir, CACHE_DIR)
    print(f"\nResults saved in {output_dir}\nReport: {report}")
    print(
        "To see your results later without running anything again: python examples/local/view.py"
    )
    if not args.no_open:
        webbrowser.open(report.as_uri())


if __name__ == "__main__":
    main()
