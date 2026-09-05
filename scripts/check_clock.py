"""Read-only device soak test. Never prints addresses, IDs or raw output."""

import argparse
import asyncio
import importlib.util
import sys
import types
from pathlib import Path

# Load the standalone client without importing the Home Assistant entry point.
package = types.ModuleType("klydo_standalone")
package.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components/klydo_clock")]
sys.modules[package.__name__] = package
spec = importlib.util.spec_from_file_location(
    "klydo_standalone.adb_client", Path(package.__path__[0]) / "adb_client.py"
)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


async def main(args):
    client = module.KlydoClient(args.host, args.port, args.timeout)
    try:
        await client.identify()
        for index in range(args.polls):
            state = await client.poll()
            if any(
                value is None
                for value in (
                    state.app_running,
                    state.app_foreground,
                    state.app_version,
                    state.free_storage_bytes,
                )
            ):
                raise RuntimeError("A required status query returned unknown")
            if (index + 1) % 10 == 0 or index + 1 == args.polls:
                print(f"Successful polls: {index + 1}", flush=True)
            if index + 1 < args.polls:
                await asyncio.sleep(args.interval)
        # Reopen the connection without rebooting or changing the clock.
        await client.close()
        await client.identify()
        await client.poll()
        print("Explicit disconnect/reconnect: passed", flush=True)
    finally:
        await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host")
    parser.add_argument("--port", type=int, default=1379)
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--polls", type=int, default=100)
    parser.add_argument("--interval", type=float, default=5)
    arguments = parser.parse_args()
    if arguments.polls < 1 or arguments.interval < 0:
        parser.error("Polls must be positive and interval nonnegative")
    asyncio.run(main(arguments))
