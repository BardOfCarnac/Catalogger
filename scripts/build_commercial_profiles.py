#!/usr/bin/env python3
"""Build Vend-R commercial profiles from source defaults plus item-level curation."""
import gzip, json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "build/data/catalog/item-commercial-profiles.json"

manifest = json.loads((DATA/"catalog/manifest.json").read_text(encoding="utf-8"))
taxonomy = json.loads((DATA/"catalog/taxonomy.json").read_text(encoding="utf-8"))

def load_table(name):
    rows=[]
    for part in manifest["tables"][name]["parts"]:
        with gzip.open(ROOT/part["path"],"rt",encoding="utf-8") as f:
            rows.extend(json.load(f))
    return rows

def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

default_docs=[load_json(p) for p in sorted((DATA/"curation/defaults").glob("*.json"))]
if not default_docs:
    raise FileNotFoundError("No commercial defaults found")

override_rows=load_json(DATA/"curation/item-overrides.json")
for path in sorted((DATA/"curation/overrides").glob("*.json")):
    override_rows.extend(load_json(path))
item_tags=load_json(DATA/"curation/item-tags.json")

version=default_docs[0]["version"]
tax_version=default_docs[0]["taxonomy_version"]
defaults={}
for doc in default_docs:
    if doc["version"]!=version or doc["taxonomy_version"]!=tax_version:
        raise ValueError("Commercial default version mismatch")
    for row in doc["defaults"]:
        key=(row["source_category"],row["source_subcategory"])
        if key in defaults:
            raise ValueError(f"Duplicate commercial default: {key!r}")
        defaults[key]=row

items=load_table("items")
classes=load_table("item-classifications")
item_mfrs=load_table("item-manufacturers")

classes_by_item=defaultdict(list)
for row in classes: classes_by_item[row["item_id"]].append(row)
mfrs_by_item=defaultdict(list)
for row in item_mfrs: mfrs_by_item[row["item_id"]].append(row["manufacturer_id"])

overrides_by_item={}
for row in override_rows:
    if row["item_id"] in overrides_by_item:
        raise ValueError(f"Duplicate override: {row['item_id']}")
    overrides_by_item[row["item_id"]]=row

tags_by_item=defaultdict(list)
for row in item_tags: tags_by_item[row["item_id"]].append(row)

GENERIC_NAMES={
    "Medium Pistol","Heavy Pistol","Very Heavy Pistol","SMG","Heavy SMG","Shotgun",
    "Assault Rifle","Sniper Rifle","Bow","Crossbow","Grenade Launcher","Rocket Launcher",
    "Light Melee Weapon","Medium Melee Weapon","Heavy Melee Weapon","Very Heavy Melee Weapon",
    "Cyberdeck (Poor Quality)","Cyberdeck (Standard Quality)","Cyberdeck (Excellent Quality)",
    "Agent (Standard)","Compact Groundcar","High Performance Groundcar","Roadbike",
    "Super Groundcar","Superbike","Aerozep","AV-4 Multipurpose Aerodyne","AV-9 Super Aerodyne",
    "Gyrocopter","Helicopter","Cabin Cruiser","Jetski","Speedboat","Yacht"
}

def union(values):
    out=[]; seen=set()
    for v in values:
        if v not in seen:
            seen.add(v); out.append(v)
    return out

def infer_identity(item):
    if mfrs_by_item.get(item["id"]): return "branded"
    if item["name"] in GENERIC_NAMES: return "generic"
    return None

def apply_override(profile, override):
    if not override: return
    for key,value in override.get("set",{}).items():
        profile[key]=value
    for key in ("market_channels","allowed_conditions","secondary_departments"):
        if key in override.get("add",{}):
            profile[key]=union(profile.get(key,[])+override["add"][key])
        if key in override.get("remove",{}):
            remove=set(override["remove"][key])
            profile[key]=[v for v in profile.get(key,[]) if v not in remove]
    for group in ("audience","use","character"):
        add=override.get("add",{}).get("affinity_tags",{}).get(group,[])
        remove=set(override.get("remove",{}).get("affinity_tags",{}).get(group,[]))
        profile["affinity_tags"][group]=[
            v for v in union(profile["affinity_tags"].get(group,[])+add) if v not in remove
        ]
    if override.get("reason"):
        profile["curation_notes"].append(override["reason"])
    if "requires_item_curation" in override:
        profile["requires_item_curation"]=bool(override["requires_item_curation"])

profiles=[]
for item in items:
    iid=item["id"]
    mapped=[]
    for c in classes_by_item[iid]:
        key=(c["source_category"],c.get("source_subcategory"))
        if key not in defaults: raise ValueError(f"No default for {key!r} ({iid})")
        mapped.append((c,defaults[key]))
    primary=next(((c,d) for c,d in mapped if c.get("is_primary")),mapped[0])
    primary_c,primary_d=primary
    profile={
        "item_id":iid,
        "product_identity":infer_identity(item),
        "department":primary_d["department"],
        "classification_path":primary_d["classification_path"],
        "secondary_departments":union(d["department"] for _,d in mapped if d["department"]!=primary_d["department"]),
        "commodity_kind":primary_d["commodity_kind"],
        "quantity_profile":primary_d["quantity_profile"],
        "allowed_conditions":list(primary_d["allowed_conditions"]),
        "default_condition":primary_d["default_condition"],
        "supply_profile":primary_d["supply_profile"],
        "market_channels":union(ch for _,d in mapped for ch in d["market_channels"]),
        "affinity_tags":{
            "audience":union(t for _,d in mapped for t in d["audience_tags"]),
            "use":union(t for _,d in mapped for t in d["use_tags"]),
            "character":union(t for _,d in mapped for t in d["character_tags"])
        },
        "inherited_from":[{"source_category":c["source_category"],"source_subcategory":c.get("source_subcategory"),"primary":bool(c.get("is_primary"))} for c,_ in mapped],
        "requires_item_curation":any(d["requires_item_curation"] for _,d in mapped),
        "curation_notes":[],
        "profile_version":version,
        "taxonomy_version":taxonomy["version"]
    }
    apply_override(profile,overrides_by_item.get(iid))
    for row in tags_by_item.get(iid,[]):
        group=row["tag_type"]; tag=row["tag_id"]
        if tag not in profile["affinity_tags"][group]:
            profile["affinity_tags"][group].append(tag)
    if profile["default_condition"] not in profile["allowed_conditions"]:
        raise ValueError(f"default condition not allowed: {iid}")
    profiles.append(profile)

OUT.parent.mkdir(parents=True,exist_ok=True)
OUT.write_text(json.dumps(profiles,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(f"Wrote {len(profiles)} commercial profiles -> {OUT.relative_to(ROOT)}")
print(f"{sum(p['requires_item_curation'] for p in profiles)} profiles still need item-level review")
print(f"{sum(p['product_identity'] is not None for p in profiles)} profiles have known product identity")
