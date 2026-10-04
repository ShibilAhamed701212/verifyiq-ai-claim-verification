"""VerifyIQ CLI entry point.

Usage:
    verifyiq evaluate    — Run the static V1 evaluation on sample claims
    verifyiq version     — Show version
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="verifyiq",
        description="Multi-Modal Claim Verification Platform",
    )
    parser.add_argument(
        "--version", action="store_true", help="Show version and exit"
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    sub.add_parser("version", help="Show version")
    sub.add_parser(
        "evaluate",
        help="Run the static V1 evaluation on dataset/sample_claims.csv",
    )

    args = parser.parse_args()

    if args.version or args.command == "version":
        from verifyiq import __version__
        print(f"verifyiq {__version__}")
        sys.exit(0)

    if args.command == "evaluate":
        _run_evaluate(args)
    else:
        parser.print_help()
        sys.exit(1)


def _run_evaluate(args):
    import runpy
    from pathlib import Path

    import verifyiq  # noqa: F401  (makes the V1 code/ package importable)

    script = Path(verifyiq.__file__).resolve().parent.parent / "code" / "evaluation" / "static_evaluate.py"
    if not script.exists():
        print(f"Error: evaluation script not found at {script}", file=sys.stderr)
        sys.exit(1)
    try:
        from code.config import Config
        print(f"Running evaluation on {Config().sample_claims_path}...")
        # static_evaluate.py is a script (no main()); execute it as __main__.
        runpy.run_path(str(script), run_name="__main__")
        print("Evaluation complete.")
    except ImportError as e:
        print(f"Error: evaluation dependencies not available ({e})", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error during evaluation: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
