import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.extracted_kg_import_service import load_extracted_papers, scan_extracted_results


def parse_args():
    parser = argparse.ArgumentParser(description="Import relation/**/extracted.json into Neo4j.")
    parser.add_argument("--root", dest="root_path", default=None, help="Path to the relation result directory.")
    parser.add_argument("--limit", type=int, default=None, help="Limit the number of extracted.json files.")
    parser.add_argument("--clear-existing", action="store_true", help="Clear imported extracted KG before import.")
    parser.add_argument("--scan-only", action="store_true", help="Only scan extracted files; do not connect to Neo4j.")
    return parser.parse_args()


async def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("neo4j").setLevel(logging.WARNING)

    if args.scan_only:
        result = scan_extracted_results(root_path=args.root_path, limit=args.limit)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    from app.services.neo4j_service import Neo4jService

    resolved_root, papers, parse_errors = load_extracted_papers(root_path=args.root_path, limit=args.limit)

    service = Neo4jService()
    await service.initialize()
    try:
        result = await service.import_extracted_papers(
            papers,
            clear_existing=args.clear_existing,
        )
        result.update({
            "root_path": str(resolved_root),
            "parsed_file_count": len(papers),
            "parse_errors": parse_errors,
        })
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(main())
