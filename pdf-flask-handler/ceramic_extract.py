"""
陶瓷材料文献 - 实体关系提取脚本 (v2 健壮版)
参考 prompt_service.py 的 JSON 修复 + chunked_ie.py 的分块去重逻辑

用法: python ceramic_extract.py <results_dir>
"""
import os
import re
import json
import time
import sys
from pathlib import Path
from openai import OpenAI

# ── 配置 ──
API_KEY = os.getenv("API_KEY", "sk-6daa6d75b15f467db7cce6523a235d15")
BASE_URL = os.getenv("BASE_URL", "https://api.deepseek.com")
MODEL = os.getenv("MODEL_NAME", "deepseek-chat")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL, timeout=300)
CHUNK_SIZE = 8000  # 每块最大字符数

# ═══════════════════════════════════════════
# Prompt 模板
# ═══════════════════════════════════════════

ENTITY_PROMPT = """你是一位精通陶瓷材料科学的领域专家。请从以下论文文本中提取关键科学实体，用于构建材料知识图谱。

## 实体类型（8类）：

### Material（材料）
陶瓷基体材料、掺杂元素、第二相。保留化学式原始写法。
包括：压电陶瓷(PZT, BNT, KNN)、铁电体、微波介质陶瓷、结构陶瓷(SiC, Si3N4, Al2O3, ZrO2)、固体电解质(YSZ, GDC)、透明陶瓷、生物陶瓷(HA, β-TCP)、掺杂离子(La3+, Nb5+, Mn2+)、烧结助剂(CuO, Li2CO3)、玻璃相
- 如：BaTiO3, Pb(Zr0.52Ti0.48)O3, 0.5BZT-0.5BCT, MnO2-doped PZT

### Property（性能/性质）
不含具体数值(数值归PerformanceMetric)。包括：
- 电学：dielectric constant, dielectric loss, piezoelectric coefficient d33/d31, electromechanical coupling factor kp, electrical conductivity, resistivity, breakdown strength, ferroelectric polarization (Pr, Ps, Ec)
- 热学：thermal conductivity, thermal expansion, Curie temperature (Tc), specific heat
- 力学：flexural strength, fracture toughness (KIC), Vickers hardness, Young's modulus
- 光学：transmittance, refractive index, band gap
- 其他：relative density, porosity, grain size

### ProcessMethod（制备工艺）
- 粉体：solid-state reaction, sol-gel, hydrothermal, co-precipitation, molten salt, ball milling, calcination
- 成型：dry pressing, cold isostatic pressing, tape casting, slip casting, 3D printing
- 烧结：pressureless sintering, hot pressing, spark plasma sintering (SPS), microwave sintering, two-step sintering, flash sintering
- 后处理：annealing, poling, polarization, grinding

### Application（应用）
capacitor, MLCC, sensor, actuator, ultrasonic transducer, SOFC, thermal barrier coating, cutting tool, biomedical implant, catalyst, IR window, microwave resonator, filter, FeRAM

### Microstructure（微观结构/相）
perovskite, spinel, fluorite, tetragonal, rhombohedral, cubic, monoclinic, morphotropic phase boundary (MPB), grain boundary, domain wall, pore, core-shell, precipitate

### Characterization（表征）
XRD, SEM, TEM, HRTEM, EDS, XPS, Raman, FTIR, DSC, TGA, impedance spectroscopy, P-E loop, d33 meter, Vickers indentation, Archimedes method, AFM, PFM

### PerformanceMetric（性能指标=数值+单位）
每个量化数据点单独提取，数值和单位必须保留在name中。
如 "d33 = 450 pC/N" → name: "d33 of 450 pC/N"
如 "Tc = 386°C" → name: "Curie temperature of 386°C"

### SynthesisParameter（合成参数）
sintering temperature, holding time, heating rate, atmosphere(N2/O2/Ar), ball milling time, pH, precursor concentration, annealing temperature

## 提取规则：
1. 化学式保留原文写法，精确到大小写
2. context字段保留原文30-80字作为证据
3. 缩写与全称合并（以化学式为准）
4. 尽可能多地提取，宁可多不要漏

## 示例输出：
{{
  "entities": [
    {{"name": "PZT", "type": "Material", "attributes": {{"dopant": "MnO2"}}, "context": "PZT ceramics with MnO2 doping were prepared by..."}},
    {{"name": "MnO2", "type": "Material", "attributes": {{"role": "dopant"}}, "context": "with MnO2 doping"}},
    {{"name": "solid-state reaction", "type": "ProcessMethod", "attributes": {{}}, "context": "prepared by conventional solid-state reaction"}},
    {{"name": "sintering at 1200°C", "type": "SynthesisParameter", "attributes": {{"temperature": "1200°C"}}, "context": "sintered at 1200°C"}},
    {{"name": "piezoelectric coefficient d33", "type": "Property", "attributes": {{}}, "context": "d33 reached 320 pC/N"}},
    {{"name": "d33 of 320 pC/N", "type": "PerformanceMetric", "attributes": {{"value": "320", "unit": "pC/N"}}, "context": "d33 reached 320 pC/N"}}
  ]
}}

## 论文文本：
__TEXT__

仅返回JSON，不要任何解释："""

RELATION_PROMPT = """你是陶瓷材料知识图谱专家。基于已提取的实体，发现实体间的科学关系。

## 关系类型（10类）：
1. hasProperty: Material → Property
2. producedBy: Material → ProcessMethod
3. usedIn: Material → Application
4. hasStructure: Material → Microstructure
5. characterizedBy: Material/Property → Characterization
6. hasMetric: Property → PerformanceMetric
7. dopedWith: Material → Material (dopant)
8. affects: ProcessMethod/Material → Property (标注增强/降低)
9. composedOf: Material → Material (复合材料组分)
10. synthesizedUnder: ProcessMethod → SynthesisParameter

## 提取规则：
1. 关系两端必须在已有实体列表中
2. evidence必须引用原文句子
3. 数值数据点必须通过hasMetric链接到对应Property

## 示例输出：
{{
  "relations": [
    {{"head": "PZT", "relation": "dopedWith", "tail": "MnO2", "evidence": "PZT ceramics with MnO2 doping were prepared"}},
    {{"head": "PZT", "relation": "producedBy", "tail": "solid-state reaction", "evidence": "prepared by conventional solid-state reaction"}},
    {{"head": "PZT", "relation": "hasProperty", "tail": "piezoelectric coefficient d33", "evidence": "d33 reached 320 pC/N"}},
    {{"head": "piezoelectric coefficient d33", "relation": "hasMetric", "tail": "d33 of 320 pC/N", "evidence": "d33 reached 320 pC/N"}}
  ]
}}

## 已识别实体：
__ENTITIES__

## 论文文本：
__TEXT__

仅返回JSON，不要任何解释："""


# ═══════════════════════════════════════════
# JSON 修复（参考 prompt_service.py）
# ═══════════════════════════════════════════

def repair_json(raw: str) -> str:
    """修复常见 LLM 输出 JSON 错误"""
    raw = raw.strip()

    # 去掉 markdown 代码块
    m = re.search(r'```(?:json)?\s*(.*?)\s*```', raw, re.DOTALL)
    if m:
        raw = m.group(1).strip()
    else:
        # 找第一个 { 到最后一个 }
        s = raw.find('{')
        e = raw.rfind('}')
        if s >= 0 and e > s:
            raw = raw[s:e+1]

    # 修复: 缺少逗号 (换行处)
    raw = re.sub(r'"\s*\n\s*"', '",\n  "', raw)
    # 修复: } { 之间缺逗号
    raw = re.sub(r'\}\s*\n\s*\{', '},\n{', raw)
    # 修复: ] [ 之间缺逗号
    raw = re.sub(r'\]\s*\n\s*\[', '],\n[', raw)
    # 修复: 尾随逗号
    raw = re.sub(r',\s*}', '}', raw)
    raw = re.sub(r',\s*]', ']', raw)
    # 修复: 未闭合括号
    open_braces = raw.count('{') - raw.count('}')
    open_brackets = raw.count('[') - raw.count(']')
    if open_braces > 0:
        raw += '}' * open_braces
    if open_brackets > 0:
        raw += ']' * open_brackets

    return raw


def safe_json_parse(raw: str, data_type: str = "entities"):
    """安全解析 JSON，失败返回空结构"""
    repaired = repair_json(raw)
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # 最后手段：正则提取
    result = {}
    if data_type == "entities":
        names = re.findall(r'"name"\s*:\s*"([^"]*)"', raw)
        types = re.findall(r'"type"\s*:\s*"([^"]*)"', raw)
        contexts = re.findall(r'"context"\s*:\s*"([^"]*)"', raw)
        entities = []
        for i, n in enumerate(names):
            entities.append({
                "name": n,
                "type": types[i] if i < len(types) else "",
                "context": contexts[i] if i < len(contexts) else ""
            })
        result["entities"] = entities
    elif data_type == "relations":
        heads = re.findall(r'"head"\s*:\s*"([^"]*)"', raw)
        tails = re.findall(r'"tail"\s*:\s*"([^"]*)"', raw)
        relations = re.findall(r'"relation"\s*:\s*"([^"]*)"', raw)
        evidences = re.findall(r'"evidence"\s*:\s*"([^"]*)"', raw)
        rels = []
        for i, r in enumerate(relations):
            rels.append({
                "head": heads[i] if i < len(heads) else "",
                "relation": r,
                "tail": tails[i] if i < len(tails) else "",
                "evidence": evidences[i] if i < len(evidences) else ""
            })
        result["relations"] = rels

    return result


# ═══════════════════════════════════════════
# 实体去重（参考 chunked_ie.py EntityRegistry）
# ═══════════════════════════════════════════

def normalize_name(name: str) -> str:
    """标准化实体名用于匹配"""
    return re.sub(r'[^a-z0-9一-鿿]', '', name.strip().lower())


def merge_entities(all_entities: list) -> list:
    """跨块合并重复实体"""
    merged = []
    seen = {}  # normalized_name → index

    for e in all_entities:
        if not e.get("name"):
            continue
        norm = normalize_name(e["name"])
        if norm in seen:
            idx = seen[norm]
            # 保留更长的 context
            if len(e.get("context", "")) > len(merged[idx].get("context", "")):
                merged[idx]["context"] = e["context"]
            # 合并 attributes
            if e.get("attributes"):
                merged[idx]["attributes"].update(e["attributes"])
        else:
            seen[norm] = len(merged)
            merged.append(e)

    return merged


def merge_relations(all_relations: list) -> list:
    """跨块去重关系"""
    seen = set()
    unique = []
    for r in all_relations:
        key = (r.get("head",""), r.get("relation",""), r.get("tail",""))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


# ═══════════════════════════════════════════
# LLM 调用（参考 prompt_service.py _call_llm_api）
# ═══════════════════════════════════════════

def call_llm(prompt: str, max_retry: int = 3) -> str:
    """调用 DeepSeek API，带指数退避重试"""
    for attempt in range(max_retry):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            wait = 2 ** attempt
            print(f"    API重试 {attempt+1}/{max_retry}: {e}，等待{wait}s")
            time.sleep(wait)
    return ""


# ═══════════════════════════════════════════
# 分块提取（参考 chunked_ie.py）
# ═══════════════════════════════════════════

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> list:
    """将长文本按段落边界分块"""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    paragraphs = text.split('\n')
    current = ""
    for para in paragraphs:
        if len(current) + len(para) < chunk_size:
            current += para + '\n'
        else:
            if current:
                chunks.append(current.strip())
            current = para + '\n'
    if current.strip():
        chunks.append(current.strip())
    return chunks


def extract_entities_chunked(text: str) -> list:
    """分块提取实体并去重"""
    chunks = chunk_text(text)
    all_entities = []

    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            print(f"    块 {i+1}/{len(chunks)} ({len(chunk)}字符)", end=" ")

        raw = call_llm(ENTITY_PROMPT.replace("__TEXT__", chunk))
        if not raw:
            continue

        result = safe_json_parse(raw, "entities")
        entities = result.get("entities", [])
        entities = [e for e in entities if isinstance(e, dict) and e.get("name")]

        if len(chunks) > 1:
            print(f"→ {len(entities)}实体")

        all_entities.extend(entities)

    return merge_entities(all_entities)


def extract_relations_chunked(entities: list, text: str) -> list:
    """分块提取关系并去重"""
    if not entities:
        return []

    entities_str = "\n".join(
        f"- [{i}] {e.get('name','?')} ({e.get('type','?')})"
        for i, e in enumerate(entities) if e.get('name')
    )

    chunks = chunk_text(text)
    all_relations = []

    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            print(f"    块 {i+1}/{len(chunks)}", end=" ")

        prompt = RELATION_PROMPT.replace("__ENTITIES__", entities_str).replace("__TEXT__", chunk)
        raw = call_llm(prompt)
        if not raw:
            continue

        result = safe_json_parse(raw, "relations")
        relations = result.get("relations", [])
        relations = [r for r in relations if isinstance(r, dict)
                     and r.get("head") and r.get("relation") and r.get("tail")]

        if len(chunks) > 1:
            print(f"→ {len(relations)}关系")

        all_relations.extend(relations)

    return merge_relations(all_relations)


# ═══════════════════════════════════════════
# 单篇处理
# ═══════════════════════════════════════════

def process_one_paper(paper_dir: str) -> dict:
    """处理单篇论文"""
    title = os.path.basename(paper_dir)
    out_path = os.path.join(paper_dir, "extracted.json")

    # 找 md 文件
    md_path = os.path.join(paper_dir, f"{title}.md")
    if not os.path.exists(md_path):
        mds = sorted([f for f in os.listdir(paper_dir) if f.endswith(".md")])
        md_path = os.path.join(paper_dir, mds[0]) if mds else ""

    # 找 json 文件
    json_path = os.path.join(paper_dir, "content_list.json")
    if not os.path.exists(json_path):
        jsons = sorted([f for f in os.listdir(paper_dir)
                       if f.endswith(".json") and f not in ("meta.json", "extracted.json")])
        json_path = os.path.join(paper_dir, jsons[0]) if jsons else ""

    # 读取文本
    text = ""
    if os.path.exists(md_path):
        with open(md_path, "r", encoding="utf-8") as f:
            text = f.read()

    # md 太短时补 json
    if os.path.exists(json_path) and (not text or len(text) < 500):
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                jdata = json.load(f)
            for block in jdata:
                if isinstance(block, dict) and block.get("text"):
                    text += block["text"] + "\n"
        except:
            pass

    if not text or len(text.strip()) < 200:
        return {"error": "text too short", "title": title}

    print(f"  文本: {len(text)}字符, {len(chunk_text(text))}块")

    # 1. 提取实体
    entities = extract_entities_chunked(text)
    print(f"  实体: {len(entities)}个")

    # 2. 提取关系
    relations = extract_relations_chunked(entities, text)
    print(f"  关系: {len(relations)}个")

    result = {
        "title": title,
        "entities": entities,
        "relations": relations,
        "entity_count": len(entities),
        "relation_count": len(relations),
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


# ═══════════════════════════════════════════
# 批量处理
# ═══════════════════════════════════════════

def batch_process(results_dir: str):
    papers = []
    for item in sorted(os.listdir(results_dir)):
        paper_dir = os.path.join(results_dir, item)
        if not os.path.isdir(paper_dir):
            continue
        if os.path.exists(os.path.join(paper_dir, "extracted.json")):
            continue
        # 必须有 md 或 json
        has_content = any(f.endswith(".md") or f.endswith(".json")
                         for f in os.listdir(paper_dir))
        if not has_content:
            continue
        papers.append(paper_dir)

    total = len(papers)
    print(f"待处理: {total} 篇")
    print("=" * 50)

    for i, paper_dir in enumerate(papers):
        title = os.path.basename(paper_dir)[:70]
        print(f"\n[{i+1}/{total}] {title}")

        try:
            result = process_one_paper(paper_dir)
            if "error" in result:
                print(f"  ⚠ {result['error']}")
            else:
                print(f"  ✅ {result['entity_count']}实体 {result['relation_count']}关系")
        except Exception as e:
            print(f"  ❌ {type(e).__name__}: {e}")

        time.sleep(0.5)

    print(f"\n{'='*50}")
    print(f"完成！")


if __name__ == "__main__":
    results_dir = sys.argv[1] if len(sys.argv) > 1 else "d:/CeramiKG/pdf-flask-handler/uploads/247"
    batch_process(results_dir)
