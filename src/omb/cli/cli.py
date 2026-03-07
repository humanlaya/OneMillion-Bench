import argparse

from omb import __version__
from omb.cli.execute_eval import EvalCMD


def run_cmd():
    parser = argparse.ArgumentParser(
        "OneMillion Bench Command Line tool", usage="omb <command> [<args>]"
    )
    parser.add_argument("-v", "--version", action="version", version=f"omb {__version__}")
    subparsers = parser.add_subparsers(help="omb command line helper.")

    EvalCMD.define_args(subparsers)

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        exit(1)

    cmd = args.func(args)
    cmd.execute()


if __name__ == "__main__":
    run_cmd()
