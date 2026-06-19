import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _safe_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if value in (None, ""):
        return {}
    return {"value": value}


def _json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)


def _short_hash(value: str, length: int = 16) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def _entity_key(name: str, entity_type: str) -> str:
    normalized = f"{entity_type.lower()}|{name.lower()}"
    return f"ceramic_entity_{_short_hash(normalized, 24)}"


def _paper_id_from_path(extracted_path: Path, root_path: Path) -> str:
    try:
        rel_parent = extracted_path.parent.relative_to(root_path)
        raw_id = "__".join(rel_parent.parts)
    except ValueError:
        raw_id = extracted_path.parent.name

    safe_id = re.sub(r"[^0-9A-Za-z_.-]+", "_", raw_id).strip("_")
    suffix = _short_hash(raw_id, 10)
    if not safe_id:
        return f"paper_{suffix}"
    if len(safe_id) > 120:
        safe_id = safe_id[:120].rstrip("_.-")
    return f"{safe_id}_{suffix}"


def _load_json_file(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def resolve_relation_root(root_path: Optional[str] = None) -> Path:
    if root_path:
        raw = Path(root_path).expanduser()
        candidates = [raw]
        if not raw.is_absolute():
            cwd = Path.cwd()
            service_root = Path(__file__).resolve().parents[2]
            project_root = Path(__file__).resolve().parents[3]
            candidates = [
                cwd / raw,
                service_root / raw,
                project_root / raw,
            ]
    else:
        env_root = os.getenv("EXTRACTED_KG_ROOT") or os.getenv("RELATION_ROOT")
        candidates = []
        if env_root:
            candidates.append(Path(env_root).expanduser())

        cwd = Path.cwd()
        service_root = Path(__file__).resolve().parents[2]
        project_root = Path(__file__).resolve().parents[3]
        candidates.extend(
            [
                cwd / "relation",
                cwd.parent / "relation",
                service_root / "relation",
                project_root / "relation",
                Path("/relation"),
            ]
        )

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.exists() and resolved.is_dir():
            return resolved

    searched = ", ".join(str(path) for path in candidates)
    raise FileNotFoundError(f"Cannot find extracted relation root. Searched: {searched}")


def iter_extracted_files(root_path: Path, limit: Optional[int] = None) -> Iterable[Path]:
    count = 0

    def _on_error(error: OSError) -> None:
        logger.warning("Failed to scan relation path: %s", error)

    for dirpath, dirnames, filenames in os.walk(root_path, onerror=_on_error):
        dirnames[:] = [name for name in dirnames if name != ".ipynb_checkpoints"]
        if "extracted.json" not in filenames:
            continue

        extracted_path = Path(dirpath) / "extracted.json"
        yield extracted_path
        count += 1
        if limit and count >= limit:
            return


def _load_paper_meta(extracted_path: Path) -> Dict[str, Any]:
    meta_path = extracted_path.parent / "meta.json"
    if not meta_path.exists():
        return {}
    try:
        meta = _load_json_file(meta_path)
        return meta if isinstance(meta, dict) else {}
    except Exception as exc:
        logger.warning("Failed to parse meta file %s: %s", meta_path, exc)
        return {}


def load_extracted_paper(extracted_path: Path, root_path: Path) -> Dict[str, Any]:
    raw = _load_json_file(extracted_path)
    if not isinstance(raw, dict):
        raise ValueError("extracted.json must be a JSON object")

    meta = _load_paper_meta(extracted_path)
    paper_id = _paper_id_from_path(extracted_path, root_path)
    extraction_title = _clean_text(raw.get("title"))
    title = _clean_text(meta.get("title")) or extraction_title or extracted_path.parent.name

    paper = {
        "paper_id": paper_id,
        "title": title,
        "extraction_title": extraction_title,
        "source_path": str(extracted_path),
        "relative_path": str(extracted_path.parent.relative_to(root_path)),
        "authors": _clean_text(meta.get("authors")),
        "journal": _clean_text(meta.get("journal")),
        "year": _clean_text(meta.get("year")),
        "doi": _clean_text(meta.get("doi")),
        "abstract": _clean_text(meta.get("abstract")),
        "keywords": _clean_text(meta.get("keywords")),
        "raw_entity_count": raw.get("entity_count"),
        "raw_relation_count": raw.get("relation_count"),
    }

    entities_by_name: Dict[str, Dict[str, Any]] = {}
    entities_by_key: Dict[str, Dict[str, Any]] = {}

    for index, item in enumerate(raw.get("entities") or []):
        if not isinstance(item, dict):
            continue
        name = _clean_text(item.get("name") or item.get("entity_name"))
        if not name:
            continue
        entity_type = _clean_text(item.get("type") or item.get("entity_type")) or "unknown"
        attributes = _safe_dict(item.get("attributes"))
        context = _clean_text(item.get("context") or item.get("description"))
        key = _entity_key(name, entity_type)
        entity = {
            "entity_key": key,
            "name": name,
            "type": entity_type,
            "attributes": attributes,
            "attributes_json": _json_dumps(attributes),
            "context": context,
            "source_index": index,
        }
        entities_by_key[key] = entity
        entities_by_name.setdefault(name.lower(), entity)

    skipped_relations = 0
    relations: List[Dict[str, Any]] = []

    for index, item in enumerate(raw.get("relations") or []):
        if not isinstance(item, dict):
            skipped_relations += 1
            continue

        head = _clean_text(item.get("head") or item.get("head_entity") or item.get("head_entity_name"))
        relation_type = _clean_text(item.get("relation") or item.get("relation_name") or item.get("type"))
        tail = _clean_text(item.get("tail") or item.get("tail_entity") or item.get("tail_entity_name"))
        if not head or not relation_type or not tail:
            skipped_relations += 1
            continue

        head_entity = entities_by_name.get(head.lower())
        if not head_entity:
            head_entity = {
                "entity_key": _entity_key(head, "unknown"),
                "name": head,
                "type": "unknown",
                "attributes": {},
                "attributes_json": "{}",
                "context": "",
                "source_index": None,
            }
            entities_by_key[head_entity["entity_key"]] = head_entity
            entities_by_name.setdefault(head.lower(), head_entity)

        tail_entity = entities_by_name.get(tail.lower())
        if not tail_entity:
            tail_entity = {
                "entity_key": _entity_key(tail, "unknown"),
                "name": tail,
                "type": "unknown",
                "attributes": {},
                "attributes_json": "{}",
                "context": "",
                "source_index": None,
            }
            entities_by_key[tail_entity["entity_key"]] = tail_entity
            entities_by_name.setdefault(tail.lower(), tail_entity)

        attributes = _safe_dict(item.get("attributes"))
        evidence = _clean_text(item.get("evidence") or item.get("evidence_text") or item.get("description"))
        relation_id_seed = f"{paper_id}|{index}|{head}|{relation_type}|{tail}|{evidence}"
        relations.append(
            {
                "relation_id": f"ceramic_relation_{_short_hash(relation_id_seed, 24)}",
                "paper_id": paper_id,
                "head": head,
                "head_key": head_entity["entity_key"],
                "relation_type": relation_type,
                "tail": tail,
                "tail_key": tail_entity["entity_key"],
                "evidence": evidence,
                "attributes": attributes,
                "attributes_json": _json_dumps(attributes),
                "source_index": index,
            }
        )

    entities = list(entities_by_key.values())
    paper["entity_count"] = len(entities)
    paper["relation_count"] = len(relations)
    paper["skipped_relation_count"] = skipped_relations

    return {
        "paper": paper,
        "entities": entities,
        "relations": relations,
    }


def load_extracted_papers(root_path: Optional[str] = None, limit: Optional[int] = None) -> Tuple[Path, List[Dict[str, Any]], List[Dict[str, str]]]:
    resolved_root = resolve_relation_root(root_path)
    papers: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    for extracted_path in iter_extracted_files(resolved_root, limit=limit):
        try:
            papers.append(load_extracted_paper(extracted_path, resolved_root))
        except Exception as exc:
            logger.warning("Failed to load extracted file %s: %s", extracted_path, exc)
            errors.append({"path": str(extracted_path), "error": str(exc)})

    return resolved_root, papers, errors


def scan_extracted_results(root_path: Optional[str] = None, limit: Optional[int] = None) -> Dict[str, Any]:
    resolved_root, papers, errors = load_extracted_papers(root_path=root_path, limit=limit)

    entity_types: Dict[str, int] = {}
    relation_types: Dict[str, int] = {}
    paper_summaries: List[Dict[str, Any]] = []
    total_entities = 0
    total_relations = 0
    skipped_relations = 0

    for item in papers:
        paper = item["paper"]
        total_entities += len(item["entities"])
        total_relations += len(item["relations"])
        skipped_relations += int(paper.get("skipped_relation_count") or 0)

        for entity in item["entities"]:
            entity_type = entity.get("type") or "unknown"
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1
        for relation in item["relations"]:
            relation_type = relation.get("relation_type") or "unknown"
            relation_types[relation_type] = relation_types.get(relation_type, 0) + 1

        paper_summaries.append(
            {
                "paper_id": paper["paper_id"],
                "title": paper["title"],
                "doi": paper.get("doi"),
                "year": paper.get("year"),
                "source_path": paper["source_path"],
                "entity_count": len(item["entities"]),
                "relation_count": len(item["relations"]),
                "skipped_relation_count": paper.get("skipped_relation_count", 0),
            }
        )

    return {
        "root_path": str(resolved_root),
        "file_count": len(papers) + len(errors),
        "parsed_file_count": len(papers),
        "error_count": len(errors),
        "total_entities": total_entities,
        "total_relations": total_relations,
        "skipped_relations": skipped_relations,
        "entity_types": dict(sorted(entity_types.items())),
        "relation_types": dict(sorted(relation_types.items())),
        "papers": paper_summaries,
        "errors": errors,
    }
