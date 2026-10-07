// VEND-R BACKEND NOTE: This Edge Function is the live API/backend.
// The canonical browser frontend is main/index.html on GitHub Pages.
// Catalogue data is read from the repository's main branch.

const ROOT = 'https://raw.githubusercontent.com/BardOfCarnac/Catalogger/main/';
const PARTS = [
  'data/catalog/items.v1.24.part01.json.gz','data/catalog/items.v1.24.part02.json.gz',
  'data/catalog/items.v1.24.part03.json.gz','data/catalog/items.v1.24.part04.json.gz',
  'data/catalog/items.v1.24.part05.json.gz','data/catalog/items.v1.24.part06.json.gz',
  'data/catalog/items.v1.24.part07.json.gz'
];
const CLASS_PARTS = [
  'data/catalog/item-classifications.v1.24.part01.json.gz',
  'data/catalog/item-classifications.v1.24.part02.json.gz'
];
const ITEM_MFR_PART='data/catalog/item-manufacturers.v1.24.json.gz';
const MFR_PATH='data/catalog/manufacturers.json';
const DESC_PATH='data/curation/item-descriptions.json';
const SOURCE_PARTS=[
  'data/catalog/item-sources.v1.24.part01.json.gz',
  'data/catalog/item-sources.v1.24.part02.json.gz'
];
const SOURCES_PATH='data/catalog/sources.json';
const NC2045_SUPP_PATH='data/catalog/nc2045-supplement.json';
let cache: Promise<any[]> | null = null;
let classCache: Promise<Map<string,any>> | null = null;
let mfrCache: Promise<Map<string,string[]>> | null = null;
let descCache: Promise<Map<string,string>> | null = null;
let itemSourceCache: Promise<Map<string,any[]>> | null = null;
let sourceBookCache: Promise<any[]> | null = null;
let nc2045SuppCache: Promise<any> | null = null;

async function gunzipJson(url:string){
  const r=await fetch(url,{headers:{'user-agent':'Vend-R/0.1'}});
  if(!r.ok) throw new Error('catalogue fetch failed: '+r.status);
  const ds=new DecompressionStream('gzip');
  return JSON.parse(await new Response(r.body!.pipeThrough(ds)).text());
}
function nc2045Supplement(){
  if(!nc2045SuppCache) nc2045SuppCache=fetch(ROOT+NC2045_SUPP_PATH,{headers:{'user-agent':'Vend-R/0.1'}})
    .then(async r=>{if(!r.ok)throw new Error('NC2045 supplement fetch failed: '+r.status);return await r.json()});
  return nc2045SuppCache;
}
function catalogue(){
  if(!cache) cache=Promise.all([
    Promise.all(PARTS.map(p=>gunzipJson(ROOT+p))).then(x=>x.flat()),
    nc2045Supplement()
  ]).then(([base,supp])=>base.concat(Array.isArray(supp?.items)?supp.items:[]));
  return cache;
}
function classifications(){
  if(!classCache) classCache=Promise.all([
    Promise.all(CLASS_PARTS.map(p=>gunzipJson(ROOT+p))).then(parts=>parts.flat()),
    nc2045Supplement()
  ]).then(([rows,supp])=>{
    const map=new Map<string,any>();
    for(const row of rows){
      const id=String(row.item_id);
      const current=map.get(id);
      if(!current||row.is_primary) map.set(id,row);
    }
    for(const item of (Array.isArray(supp?.items)?supp.items:[])){
      if(item?.classification) map.set(String(item.id),{item_id:String(item.id),...item.classification});
    }
    return map;
  });
  return classCache;
}
function manufacturers(){
  if(!mfrCache) mfrCache=Promise.all([
    gunzipJson(ROOT+ITEM_MFR_PART),
    fetch(ROOT+MFR_PATH,{headers:{'user-agent':'Vend-R/0.1'}}).then(async r=>{if(!r.ok)throw new Error('manufacturer fetch failed: '+r.status);return await r.json()})
  ]).then(([links,rows])=>{
    const names=new Map(rows.map((r:any)=>[String(r.id),String(r.name)]));
    const map=new Map<string,string[]>();
    for(const row of links){
      const id=String(row.item_id), name=names.get(String(row.manufacturer_id));
      if(!name)continue;
      const list=map.get(id)||[]; list.push(name); map.set(id,list);
    }
    return map;
  });
  return mfrCache;
}
function displayName(i:any){
  return String(i?.display_name||i?.name||i?.id||'Catalogue item');
}
function descriptions(){
  if(!descCache) descCache=Promise.all([
    fetch(ROOT+DESC_PATH,{headers:{'user-agent':'Vend-R/0.1'}}).then(async r=>{if(!r.ok)throw new Error('description fetch failed: '+r.status);return await r.json()}),
    nc2045Supplement()
  ]).then(([data,supp])=>{
    const map=new Map(Object.entries(data?.items||{}).map(([id,value])=>[String(id),String(value)]));
    for(const item of (Array.isArray(supp?.items)?supp.items:[])) if(item?.description) map.set(String(item.id),String(item.description));
    return map;
  });
  return descCache;
}
function sourceBooks(){
  if(!sourceBookCache) sourceBookCache=fetch(ROOT+SOURCES_PATH,{headers:{'user-agent':'Vend-R/0.1'}})
    .then(async r=>{if(!r.ok)throw new Error('source manifest fetch failed: '+r.status);return await r.json()})
    .then((rows:any[])=>Array.isArray(rows)?rows:[]);
  return sourceBookCache;
}
function itemSourceMap(){
  if(!itemSourceCache) itemSourceCache=Promise.all([
    Promise.all(SOURCE_PARTS.map(p=>gunzipJson(ROOT+p))).then(parts=>parts.flat()),
    nc2045Supplement()
  ]).then(([rows,supp])=>{
    const map=new Map<string,any[]>();
    for(const row of rows){
      const id=String(row.item_id||'');
      if(!id)continue;
      const list=map.get(id)||[];
      list.push({
        code:String(row.source_code||''),
        page:row.page==null?null:String(row.page),
        raw_reference:row.raw_reference==null?null:String(row.raw_reference)
      });
      map.set(id,list);
    }
    for(const item of (Array.isArray(supp?.items)?supp.items:[])){
      const src=item?.source;
      if(!src)continue;
      const id=String(item.id||'');
      if(!id)continue;
      const list=map.get(id)||[];
      list.push({code:String(src.code||'NC2045'),page:src.page==null?null:String(src.page),raw_reference:src.raw_reference==null?null:String(src.raw_reference)});
      map.set(id,list);
    }
    return map;
  });
  return itemSourceCache;
}
function sourceMeta(row:any){
  const code=String(row?.code||'');
  const sourceType=code.startsWith('DL:')?'official-dlc':(code==='CPCW'?'official-promo':'official-book');
  return {
    code,
    title:String(row?.title||code),
    publisher:'R. Talsorian Games',
    source_type:sourceType,
    family:'official'
  };
}
const VENDR_SOURCE={
  code:'VENDR',
  title:'Vend-R Originals',
  publisher:'Vend-R',
  source_type:'original',
  family:'vendr',
  description:'Original and inferred market material created for Vend-R.'
};
function requestedSourceCodes(u:URL){
  const raw=u.searchParams.get('sources');
  if(raw===null)return null;
  const value=raw.trim();
  if(!value||value==='-')return new Set<string>();
  return new Set(value.split(',').map(x=>x.trim()).filter(Boolean));
}
function sourceCodeFromRef(ref:any,books:any[]){
  const text=String(ref||'').trim();
  if(!text)return 'VENDR';
  if(/\bvend-?r\b/i.test(text))return 'VENDR';
  const lower=text.toLowerCase();
  const rows=books.slice().sort((a:any,b:any)=>String(b.title||'').length-String(a.title||'').length);
  for(const row of rows){
    const title=String(row.title||'').trim();
    if(title&&lower.startsWith(title.toLowerCase()))return String(row.code);
  }
  return null;
}
function sourceRowsForItem(id:any,sourceMap:Map<string,any[]>,books:any[]){
  const names=new Map(books.map((row:any)=>[String(row.code),String(row.title)]));
  return (sourceMap.get(String(id))||[]).map((row:any)=>({
    code:String(row.code),
    title:names.get(String(row.code))||String(row.code),
    page:row.page??null,
    raw_reference:row.raw_reference??null,
    family:'official'
  }));
}
function itemAllowed(id:any,sourceMap:Map<string,any[]>,active:Set<string>|null){
  if(active===null)return true;
  return (sourceMap.get(String(id))||[]).some((row:any)=>active.has(String(row.code)));
}
function profileAllowed(p:any,active:Set<string>|null,books:any[]){
  if(active===null)return true;
  const code=sourceCodeFromRef(p?.source_ref,books);
  return Boolean(code&&active.has(code));
}
function offeringSourceCode(offering:any,books:any[]){
  if(offering?.is_inferred)return 'VENDR';
  return sourceCodeFromRef(offering?.source_ref,books)||'VENDR';
}
function offeringAllowed(offering:any,active:Set<string>|null,books:any[]){
  return active===null||active.has(offeringSourceCode(offering,books));
}
function localSourceRows(offering:any,books:any[]){
  const code=offeringSourceCode(offering,books);
  if(code==='VENDR')return [{...VENDR_SOURCE}];
  const row=books.find((x:any)=>String(x.code)===code);
  return row?[{...sourceMeta(row)}]:[];
}

const SB_URL=Deno.env.get('SUPABASE_URL')!;
const SB_KEY=Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;
const JH={
  'content-type':'application/json; charset=utf-8',
  'access-control-allow-origin':'*',
  'access-control-allow-headers':'authorization, x-client-info, apikey, content-type',
  'access-control-allow-methods':'GET, POST, OPTIONS'
};
function out(v:any,status=200){return new Response(JSON.stringify(v),{status,headers:JH})}
const serviceHeaders={apikey:SB_KEY,Authorization:'Bearer '+SB_KEY,'content-type':'application/json'};
async function db(table:string,query=''){
  const r=await fetch(SB_URL+'/rest/v1/'+table+(query?'?'+query:''),{headers:serviceHeaders});
  if(!r.ok) throw new Error(table+': '+r.status+' '+await r.text());
  return await r.json();
}
async function dbInsert(table:string,row:any){
  const r=await fetch(SB_URL+'/rest/v1/'+table,{method:'POST',headers:{...serviceHeaders,Prefer:'return=representation'},body:JSON.stringify(row)});
  if(!r.ok) throw new Error(table+': '+r.status+' '+await r.text());
  return await r.json();
}
async function dbUpsert(table:string,row:any,onConflict:string){
  const url=SB_URL+'/rest/v1/'+table+'?on_conflict='+encodeURIComponent(onConflict);
  const r=await fetch(url,{method:'POST',headers:{...serviceHeaders,Prefer:'resolution=merge-duplicates,return=representation'},body:JSON.stringify(row)});
  if(!r.ok) throw new Error(table+': '+r.status+' '+await r.text());
  return await r.json();
}
async function rpc(name:string,args:any){
  const r=await fetch(SB_URL+'/rest/v1/rpc/'+name,{method:'POST',headers:serviceHeaders,body:JSON.stringify(args)});
  if(!r.ok){
    const body=await r.text();
    const e:any=new Error(body); e.status=r.status; throw e;
  }
  return await r.json();
}
async function authenticatedUser(req:Request){
  const auth=req.headers.get('authorization')||'';
  if(!auth.toLowerCase().startsWith('bearer '))return null;
  const r=await fetch(SB_URL+'/auth/v1/user',{headers:{apikey:SB_KEY,Authorization:auth}});
  if(!r.ok)return null;
  return await r.json();
}
function parts(v:any){return String(v||'').split('|').map(x=>x.trim()).filter(Boolean)}

const SUB_DEPT:any={
  'Ammunition':'ammunition-ordnance','Grenades':'ammunition-ordnance','Explosives':'ammunition-ordnance',
  'Armor':'armor-protection','Assisted Combat Power Armor (ACPA)':'armor-protection',
  'Medium Pistols':'weapons','Heavy Pistols':'weapons','Very Heavy Pistols':'weapons','SMG':'weapons','Heavy SMG':'weapons',
  'Shotguns':'weapons','Assault Rifles':'weapons','Sniper Rifles':'weapons','Bows and Crossbows':'weapons',
  'Light Melee Weapons':'weapons','Medium Melee Weapons':'weapons','Heavy Melee Weapons':'weapons','Very Heavy Melee Weapons':'weapons',
  'Thrown Weapons':'weapons','Grenade Launchers':'weapons','Rocket Launchers':'weapons','Machine Guns':'weapons',
  'Weapon Attachments':'weapon-parts',
  'Agents':'electronics-comms','Apps and Software':'electronics-comms',
  'Cyberdecks':'netrunning','Cyberdeck Hardware':'netrunning','Attacker Programs':'netrunning','Defender Programs':'netrunning',
  'Booster Programs':'netrunning','Black ICE':'netrunning','Demons':'netrunning','NET Architecture':'netrunning','Netrunning Accessories':'netrunning',
  'BioExotic Packages':'cyberware','Borgware':'cyberware','Chipware':'cyberware','Cyberaudio':'cyberware','Cyberfingers':'cyberware',
  'Cyberlimbs':'cyberware','Cyberoptics':'cyberware','Cyberware Alternatives':'cyberware','Cyberware Enhancements':'cyberware',
  'External Body Cyberware':'cyberware','External Linear Frames':'cyberware','FBC Bodies':'cyberware','Internal Body Cyberware':'cyberware','Neuralware':'cyberware',
  'Pharmaceuticals':'medical-chemical','Poisons':'medical-chemical','Street Drugs':'medical-chemical','Medical Services':'medical-chemical',
  'Fashion Styles':'fashion-personal','Specific Fashions':'fashion-personal','Fashionware':'fashion-personal','Fashion Linings':'fashion-personal',
  'Foodstuffs':'food-consumables','Drinks (and similar substances served in bars and pubs)':'food-consumables',
  'Furniture Sets':'housing-property','Home Accessories':'housing-property','Housing':'housing-property','Headquarters Improvements':'housing-property',
  'Ground Vehicle Types':'vehicles-mobility','Ground Vehicles':'vehicles-mobility','Air Vehicle Types':'vehicles-mobility','Air Vehicles':'vehicles-mobility',
  'Sea Vehicle Types':'vehicles-mobility','Sea Vehicles':'vehicles-mobility','Unique Vehicles':'vehicles-mobility','Vehicle Upgrades':'vehicles-mobility','Bicycle Upgrades':'vehicles-mobility',
  'Personal Drones':'drones-robotics','Cyberpets®':'drones-robotics',
  'Elflines Online the TCG Cards':'virtual-goods-games','In-Game Armory (cost is in in-game currency)':'virtual-goods-games','In-Game Purchases':'virtual-goods-games',
  'General':'general-equipment','General Gear':'general-equipment','Active Defenses (Costs can change if DVs change)':'general-equipment',
  'Emplaced Defenses':'general-equipment','Environmental Defenses':'general-equipment','Punknaught Parts':'general-equipment'
};
function classification(i:any,classMap?:Map<string,any>){return classMap?.get(String(i?.id))||null}
function department(i:any,classMap?:Map<string,any>){
  const cls=classification(i,classMap), sub=String(cls?.source_subcategory||'');
  if(SUB_DEPT[sub]) return SUB_DEPT[sub];
  if(i.primary_department) return String(i.primary_department);
  const n=String(i.name||'').toLowerCase();
  if(/shotgun|rifle|pistol|smg|weapon|gun|blade|melee|bow|crossbow/.test(n)) return 'weapons';
  if(/ammo|ammunition|shell|round|grenade|rocket/.test(n)) return 'ammunition-ordnance';
  if(/armor|armour|helmet|shield/.test(n)) return 'armor-protection';
  if(/cyber|implant|neural|cybereye|cyberarm/.test(n)) return 'cyberware';
  if(/agent|radio|computer|camera|electronics|software|app/.test(n)) return 'electronics-comms';
  if(/med|drug|pharma|antibiotic|stim/.test(n)) return 'medical-chemical';
  if(/car|bike|vehicle|aerodyne|boat|helicopter/.test(n)) return 'vehicles-mobility';
  return null;
}
function matchRule(p:any){return p?.data?.catalog_match||null}
function textHit(i:any,terms:any[]){const n=(String(i?.name||'')+' '+displayName(i)).toLowerCase();return (terms||[]).some(t=>n.includes(String(t).toLowerCase()))}
function ruleAllows(p:any,i:any,classMap:Map<string,any>,mfrMap:Map<string,string[]>){
  const rule=matchRule(p);
  if(!rule) return {allow:true,boost:0};
  if(rule.strategy==='no_catalog_stock'||rule.strategy==='local_only') return {allow:false,boost:0};
  const d=department(i,classMap), sub=String(classification(i,classMap)?.source_subcategory||'');
  const rel=relationKey(i,classMap);
  const itemName=String(i?.display_name||i?.name||'').toLowerCase();
  if(rule.strategy==='used_specialist' && quantityClass(i,classMap)==='continuous' && rule.allow_continuous!==true) return {allow:false,boost:0};

  // Semantic shelf constraints sit above broad department mapping. They let a
  // shop say "ordinary gear, yes; hotels/drones/vehicle parts, no" without
  // abandoning canonical catalogue stock entirely.
  const allowedRelPrefixes=rule.allowed_relation_prefixes||[];
  if(allowedRelPrefixes.length&&!allowedRelPrefixes.some((x:string)=>rel.startsWith(String(x).toLowerCase()))) return {allow:false,boost:0};
  const excludedRelPrefixes=rule.excluded_relation_prefixes||[];
  if(excludedRelPrefixes.some((x:string)=>rel.startsWith(String(x).toLowerCase()))) return {allow:false,boost:0};
  const excludedNameTerms=rule.excluded_name_terms||[];
  if(excludedNameTerms.some((x:string)=>itemName.includes(String(x).toLowerCase()))) return {allow:false,boost:0};

  const hardSubs=rule.allowed_subcategories||[];
  const hardSubMatch=hardSubs.length>0&&hardSubs.includes(sub);
  const allowedDeps=rule.allowed_departments||[];
  // A specific subcategory rule is stronger than the broad department mapping.
  // This matters for crossover families such as Fashionware, which is catalogued
  // under fashion-personal but is legitimately sold by cosmetic cyberware shops.
  if(allowedDeps.length&&!hardSubMatch&&(!d||!allowedDeps.includes(d))) return {allow:false,boost:0};
  if((rule.exclude_departments||[]).includes(d)) return {allow:false,boost:0};
  if(hardSubs.length&&!hardSubMatch) return {allow:false,boost:0};
  const itemMfrs=mfrMap.get(String(i.id))||[];
  const required=rule.required_manufacturers||[];
  if(required.length){
    const requiredMatch=itemMfrs.some(x=>required.includes(x));
    // Factory/showroom profiles may use generic catalogue entries as their
    // house-branded equivalent, but must not inherit a rival named brand.
    if(!requiredMatch&&itemMfrs.length) return {allow:false,boost:0};
    if(!requiredMatch&&!itemMfrs.length&&rule.allow_unbranded===false) return {allow:false,boost:0};
  }
  let boost=0;
  if((rule.preferred_subcategories||[]).includes(sub)) boost+=35;
  if((rule.preferred_manufacturers||[]).some((x:string)=>itemMfrs.includes(x))) boost+=28;
  const specialistTerms=rule.required_name_terms||rule.preferred_name_terms||rule.name_boost_terms||[];
  const specialistHit=textHit(i,specialistTerms);
  if(rule.strategy==='specialist_terms'&&specialistTerms.length&&!specialistHit) return {allow:false,boost:0};
  if(specialistHit) boost+=rule.strategy==='specialist_terms'?42:24;
  if(required.length&&itemMfrs.some(x=>required.includes(x))) boost+=45;
  // Tiered shops expose only the public subset through ordinary browsing.
  if(rule.strategy==='tiered'&&rule.public_subcategories?.length&&(!sub||!rule.public_subcategories.includes(sub))) return {allow:false,boost:0};
  return {allow:true,boost};
}
function score(p:any,i:any,classMap:Map<string,any>,mfrMap:Map<string,string[]>){
  if(!['DIRECT_SELLER','EVENT_MARKET','HYBRID_DIRECT_EVENT'].includes(String(p.stock_mode||''))) return null;
  const gate=ruleAllows(p,i,classMap,mfrMap); if(!gate.allow) return null;
  const d=department(i,classMap), pri=parts(p.primary_departments), sec=parts(p.secondary_departments);
  let s=0;
  const rule=matchRule(p)||{};
  const strategy=String(rule.strategy||'');
  const hardSubs=rule.allowed_subcategories||[];
  const sub=sourceSubcategory(i,classMap);
  const hardSubMatch=hardSubs.length>0&&hardSubs.includes(sub);
  if(strategy==='event_market'&&!pri.length&&!sec.length){
    if(!d||['housing-property','services-entertainment'].includes(d)) return null;
    s=70;
  }else if(d&&pri.includes(d)) s=100;
  else if(d&&sec.includes(d)) s=55;
  else if(hardSubMatch) s=90;
  else if(d) return null;
  else s=15;
  const max=Number(matchRule(p)?.max_base_price_eb??p.max_base_price_eb), price=basePrice(i);
  if(Number.isFinite(max)&&max>0&&price!==null&&price>max) return null;
  if(p.breadth_profile==='broad') s+=10;
  if(p.assignment_confidence==='HIGH') s+=5;
  const itemMfrs=mfrMap.get(String(i.id))||[];
  if(d==='weapons'&&!itemMfrs.length&&!(rule.required_manufacturers||[]).length) s+=30;
  s+=availabilityAdjustment(p,i);
  return s+gate.boost;
}

function basePrice(i:any){
  const bp=i?.base_price;
  if(bp&&typeof bp==='object'){
    const lo=Number(bp.min), hi=Number(bp.max);
    if(Number.isFinite(lo)&&Number.isFinite(hi)) return (lo+hi)/2;
    if(Number.isFinite(lo)) return lo;
    if(Number.isFinite(hi)) return hi;
  }
  for(const key of ['price_min','price_max','price','cost_value','cost']){
    const v=Number(i?.[key]); if(Number.isFinite(v)) return v;
  }
  return null;
}
function priceTier(i:any){
  const raw=String(i?.base_price?.tier||i?.price_tier||'').trim();
  if(raw)return raw;
  const p=basePrice(i);
  if(p===null)return 'Unknown';
  if(p<=10)return 'Cheap';
  if(p<=20)return 'Everyday';
  if(p<=50)return 'Costly';
  if(p<=100)return 'Premium';
  if(p<=500)return 'Expensive';
  if(p<=1000)return 'Very Expensive';
  if(p<=5000)return 'Luxury';
  return 'Super Luxury';
}
function availabilityInfo(i:any){
  const tier=priceTier(i);
  const key=tier.toLowerCase().replace(/[^a-z]/g,'');
  if(key==='expensive')return {key:'restricted',label:'Restricted circulation',rank:1,tier};
  if(key==='veryexpensive')return {key:'scarce',label:'Scarce',rank:2,tier};
  if(key==='luxury')return {key:'rare_market',label:'Rare market',rank:3,tier};
  if(key==='superluxury')return {key:'exceptional',label:'Exceptional',rank:4,tier};
  return {key:'common',label:'Common circulation',rank:0,tier};
}
function availabilityContext(p:any){
  const mode=String(p?.stock_mode||'');
  const cap=String(p?.supply_capability||'ordinary').toLowerCase();
  const channels=parts(p?.market_channel_override).map((x:string)=>x.toLowerCase());
  const strategy=String(matchRule(p)?.strategy||'').toLowerCase();
  if(
    mode==='EVENT_MARKET' ||
    channels.includes('black_market') ||
    (String(p?.primary_archetype||'')==='night-market-stall'&&mode!=='DIRECT_SELLER')
  ) return 'market';
  if(
    ['specialist','bespoke','corporate','clandestine'].includes(cap) ||
    channels.some((x:string)=>['specialist','direct_order','grey_market'].includes(x)) ||
    ['manufacturer','specialist'].includes(strategy)
  ) return 'specialist';
  if(
    ['irregular','nomad'].includes(cap) ||
    channels.some((x:string)=>['pawn','street','nomad'].includes(x))
  ) return 'irregular';
  return 'ordinary';
}
function availabilityAdjustment(p:any,i:any){
  const rank=availabilityInfo(i).rank;
  const context=availabilityContext(p);
  const table:any={
    ordinary:[18,-8,-32,-52,-82],
    irregular:[12,0,-16,-28,-62],
    specialist:[8,10,4,2,-34],
    market:[2,10,14,20,-8]
  };
  return (table[context]||table.ordinary)[rank]??0;
}

function relationKey(i:any,classMap?:Map<string,any>){
  const cls=classification(i,classMap);
  if(cls){
    const cat=String(cls.source_category||'').trim().toLowerCase();
    const sub=String(cls.source_subcategory||'').trim().toLowerCase();
    if(cat||sub) return (cat+':'+sub).replace(/\s+/g,'-');
  }
  return department(i,classMap)||'other';
}
function assortmentPlan(p:any){
  const a=p?.data?.assortment||{};
  // Keep the live service aligned with data/stocking/model.json. Breadth is the
  // number of distinct catalogue lines a seller can plausibly carry; physical
  // shop scale then nudges that total up or down. Curated capacities can make a
  // shop larger, but no longer drag it below the model's sensible floor.
  const breadthTotals:any={compact:12,small:18,medium:28,broad:40,extensive:60};
  const scaleFactors:any={tiny:.60,small:.78,medium:1.00,large:1.20,huge:1.45};
  const breadth=String(p.breadth_profile||'medium').toLowerCase();
  const scale=String(p?.data?.shop_scale||'medium').toLowerCase();
  const target=Math.max(1,Math.round((breadthTotals[breadth]||28)*(scaleFactors[scale]||1)));
  const modelLo=Math.max(1,Math.round(target*.80));
  const modelHi=Math.max(modelLo,Math.round(target*1.20));
  const explicitLo=Number(a.capacity_min), explicitHi=Number(a.capacity_max);
  const lo=Math.max(modelLo,Number.isFinite(explicitLo)?explicitLo:0);
  const hi=Math.max(lo,modelHi,Number.isFinite(explicitHi)?explicitHi:0);
  const total=lo+(hi>lo?stableIndex('cycle1|'+p.entity_id+'|capacity',hi-lo+1):0);
  const core=Math.max(1,Math.round(total*.30));
  const regular=Math.max(0,Math.round(total*.45));
  const occasional=Math.max(0,total-core-regular);
  return {core,regular,occasional,total};
}
function defaultShape(p:any){
  const pri=parts(p.primary_departments), sec=parts(p.secondary_departments);
  const present=new Set([...pri,...sec]);
  const defs:any={
    'general-store':[['food-consumables',.58],['general-equipment',.32],['electronics-comms',.05],['fashion-personal',.05]],
    'weapons-dealer':[['weapons',.55],['ammunition-ordnance',.25],['armor-protection',.10],['weapon-parts',.10]],
    'electronics-shop':[['electronics-comms',.65],['netrunning',.25],['virtual-goods-games',.10]],
    'netrunner-supplier':[['netrunning',.70],['electronics-comms',.20],['virtual-goods-games',.10]],
    'cyberware-clinic':[['cyberware',.70],['electronics-comms',.15],['medical-chemical',.15]],
    'fashion-boutique':[['fashion-personal',.75],['armor-protection',.15],['cyberware',.10]],
    'pawn-shop':[['general-equipment',.40],['electronics-comms',.30],['weapons',.15],['fashion-personal',.15]],
    'entertainment-vendor':[['virtual-goods-games',.50],['services-entertainment',.30],['electronics-comms',.10],['general-equipment',.10]],
    'vehicle-dealer':[['vehicles-mobility',.80],['general-equipment',.20]],
    'pharmacy':[['medical-chemical',.80],['general-equipment',.20]]
  };
  const raw=defs[String(p.primary_archetype||'')]||[];
  const kept=raw.filter((x:any)=>present.has(x[0]));
  const sum=kept.reduce((n:number,x:any)=>n+Number(x[1]),0);
  if(kept.length<2||sum<=0)return [];
  return kept.map((x:any)=>({label:x[0],weight:Number(x[1])/sum,departments:[x[0]]}));
}
function itemMatchesBucket(i:any,b:any,classMap:Map<string,any>){
  const sub=String(classification(i,classMap)?.source_subcategory||'');
  const dep=department(i,classMap);
  const subs=Array.isArray(b?.subcategories)?b.subcategories:[];
  const deps=Array.isArray(b?.departments)?b.departments:[];
  const excludedSubs=Array.isArray(b?.exclude_subcategories)?b.exclude_subcategories:[];
  const excludedDeps=Array.isArray(b?.exclude_departments)?b.exclude_departments:[];
  if(excludedSubs.includes(sub)||excludedDeps.includes(dep))return false;
  if(subs.length&&subs.includes(sub))return true;
  if(deps.length&&dep&&deps.includes(dep))return true;
  return !subs.length&&!deps.length;
}

function lifecycle(p:any){return p?.data?.stock_lifecycle||{mode:'scheduled',cadence_hours:168,cadence_label:'Weekly',turnover:'steady',rotation:{core_cycles:null,regular_cycles:3,occasional_cycles:1}}}
function cycleInfo(p:any,nowMs=Date.now()){
  const l=lifecycle(p), hours=Number(l.cadence_hours);
  if(!Number.isFinite(hours)||hours<=0)return {cycle:1,next_restock_at:null,cadence_label:l.cadence_label||'No shelf stock',turnover:l.turnover||null,stock_day:Math.floor(nowMs/86400000)};
  const ms=hours*3600000;
  const cycle=Math.floor(nowMs/ms);
  const next=(cycle+1)*ms;
  return {cycle,next_restock_at:new Date(next).toISOString(),cadence_label:l.cadence_label||null,turnover:l.turnover||null,stock_day:Math.floor(nowMs/86400000)};
}
function roleEpoch(p:any,role:string,cycle:number){
  const rot=lifecycle(p)?.rotation||{};
  const raw=rot[role+'_cycles'];
  if(raw===null||raw===undefined)return 0;
  const n=Math.max(1,Number(raw)||1);
  return Math.floor(cycle/n);
}
function roleOrder(p:any,ranked:any[],role:string,cycle:number){
  const epoch=roleEpoch(p,role,cycle);
  const jitter=role==='core'?5:role==='regular'?18:38;
  return ranked.slice().sort((a:any,b:any)=>{
    const aj=(stableIndex(p.entity_id+'|'+role+'|'+epoch+'|'+a.item.id,2001)-1000)/1000*jitter;
    const bj=(stableIndex(p.entity_id+'|'+role+'|'+epoch+'|'+b.item.id,2001)-1000)/1000*jitter;
    return (Number(b.fit)+bj)-(Number(a.fit)+aj)||String(a.item.id).localeCompare(String(b.item.id));
  });
}
function shapeQuotas(shape:any[],total:number,seed:string){
  if(!shape.length||total<=0)return [];
  const weights=shape.map((b:any)=>Math.max(0,Number(b?.weight)||0));
  let sum=weights.reduce((n:number,x:number)=>n+x,0);
  if(sum<=0){sum=shape.length;for(let i=0;i<weights.length;i++)weights[i]=1}
  const raw=weights.map((w:number)=>total*w/sum);
  const quotas=raw.map((x:number)=>Math.floor(x));
  let remaining=total-quotas.reduce((n:number,x:number)=>n+x,0);
  const order=raw.map((x:number,i:number)=>({i,frac:x-Math.floor(x)}))
    .sort((a:any,b:any)=>b.frac-a.frac||
      stableIndex(seed+'|quota|'+a.i,2147483647)-stableIndex(seed+'|quota|'+b.i,2147483647));
  for(let k=0;k<remaining;k++)quotas[order[k%order.length].i]++;
  return quotas;
}
function selectAssortment(p:any,ranked:any[],plan:any,classMap:Map<string,any>,cycle:number){
  const explicit=Array.isArray(p?.data?.assortment?.shape)?p.data.assortment.shape:[];
  const shape=explicit.length?explicit:defaultShape(p);
  const quotas=shapeQuotas(shape,Number(plan.total||0),String(p.entity_id)+'|'+cycle);
  const used=new Set<string>();
  const selected:any[]=[];
  const roles=['core','regular','occasional'];
  for(const role of roles){
    const count=Math.max(0,Number(plan[role]||0));
    if(count<=0)continue;
    const ordered=roleOrder(p,ranked,role,cycle);
    const roleSelected:any[]=[];
    while(roleSelected.length<count&&shape.length&&quotas.some((q:number)=>q>0)){
      const bucketOrder=shape.map((_:any,i:number)=>i)
        .filter((i:number)=>quotas[i]>0)
        .sort((a:number,b:number)=>quotas[b]-quotas[a]||
          stableIndex(String(p.entity_id)+'|'+cycle+'|'+role+'|bucket|'+a,2147483647)-
          stableIndex(String(p.entity_id)+'|'+cycle+'|'+role+'|bucket|'+b,2147483647));
      let progressed=false;
      for(const bi of bucketOrder){
        if(roleSelected.length>=count)break;
        const bucket=shape[bi];
        const row=ordered.find((candidate:any)=>{
          const id=String(candidate.item.id);
          return !used.has(id)&&itemMatchesBucket(candidate.item,bucket,classMap);
        });
        if(!row)continue;
        const id=String(row.item.id);
        roleSelected.push({...row,role});
        used.add(id);
        quotas[bi]=Math.max(0,quotas[bi]-1);
        progressed=true;
      }
      if(!progressed)break;
    }
    const fallbackRows=(explicit.length&&p?.data?.assortment?.shape_allow_fallback!==true)
      ? ordered.filter((row:any)=>shape.some((bucket:any)=>itemMatchesBucket(row.item,bucket,classMap)))
      : ordered;
    for(const row of fallbackRows){
      if(roleSelected.length>=count)break;
      const id=String(row.item.id);
      if(used.has(id))continue;
      roleSelected.push({...row,role});used.add(id);
    }
    selected.push(...roleSelected);
  }
  return selected;
}
function depthMultiplier(p:any){
  const m:any={shallow:.65,normal:1,deep:1.65,warehouse:2.6};
  return m[String(p.depth_profile||'normal').toLowerCase()]||1;
}
function scaleQuantityMultiplier(p:any){
  const m:any={tiny:.8,small:.9,medium:1,large:1.18,huge:1.4};
  return m[String(p?.data?.shop_scale||'medium').toLowerCase()]||1;
}
function quantityClass(i:any,classMap:Map<string,any>){
  const sub=String(classification(i,classMap)?.source_subcategory||'');
  const dep=department(i,classMap);
  const itemName=String(i?.display_name||i?.name||'').trim().toLowerCase();
  if(itemName==='live chicken')return 'low';
  if(['Apps and Software','Attacker Programs','Defender Programs','Booster Programs','Black ICE','Demons','In-Game Purchases','Medical Services'].includes(sub))return 'continuous';
  if(['Ground Vehicle Types','Ground Vehicles','Air Vehicle Types','Air Vehicles','Sea Vehicle Types','Sea Vehicles','Unique Vehicles','Housing','Headquarters Improvements'].includes(sub))return 'singular';
  if(['Ammunition','Foodstuffs','Drinks (and similar substances served in bars and pubs)'].includes(sub))return 'bulk';
  if(['Pharmaceuticals','Street Drugs','Poisons','Fashion Styles','Specific Fashions','Fashionware','Elflines Online the TCG Cards'].includes(sub))return 'high';
  if(dep==='weapons'||dep==='armor-protection'||dep==='cyberware'||dep==='vehicles-mobility')return 'low';
  return 'normal';
}
function cycleQuantity(p:any,i:any,classMap:Map<string,any>,role:string,cycle:number){
  const qclass=quantityClass(i,classMap);
  if(qclass==='continuous')return null;
  let lo=2,hi=7;
  if(qclass==='singular'){lo=1;hi=1}
  else if(qclass==='low'){lo=1;hi=4}
  else if(qclass==='high'){lo=4;hi=12}
  else if(qclass==='bulk'){lo=8;hi=24}
  const tier=String(i?.base_price?.tier||i?.price_tier||'').toLowerCase();
  if(tier.includes('super luxury')||tier.includes('luxury')){lo=1;hi=Math.min(hi,2)}
  else if(tier.includes('very expensive')){lo=1;hi=Math.min(hi,3)}
  else if(tier.includes('expensive')){lo=Math.min(lo,2);hi=Math.min(hi,5)}
  const span=Math.max(1,hi-lo+1);
  const raw=lo+stableIndex('qty|'+cycle+'|'+p.entity_id+'|'+i.id,span);
  const roleMul=role==='core'?1.35:(role==='occasional'?0.70:1);
  return Math.max(1,Math.round(raw*depthMultiplier(p)*scaleQuantityMultiplier(p)*roleMul));
}
function pricingMultiplier(p:any){
  // Shop character nudges shelf prices, but RED's canonical value remains the
  // mechanical settlement price. Keep the fiction lively without turning the
  // catalogue into a second economy simulation.
  const m:any={bargain:.94,fair:1,premium:1.06,gouging:1.12};
  return m[String(p?.pricing_style||'fair').toLowerCase()]||1;
}
function roundMarketPrice(value:number){
  if(value<10)return Math.round(value*100)/100;
  if(value<100)return Math.round(value);
  if(value<1000)return Math.round(value/5)*5;
  if(value<5000)return Math.round(value/10)*10;
  return Math.round(value/50)*50;
}
function cyclePrice(p:any,i:any,cycle:number){
  const base=basePrice(i); if(base===null) return null;
  // Deterministic per seller × item × stock generation: prices look like a
  // market but do not reshuffle simply because somebody reloads the page.
  const jitter=(stableIndex('market-price|'+cycle+'|'+p.entity_id+'|'+i.id,1201)-600)/10000;
  const multiplier=Math.max(.82,Math.min(1.18,pricingMultiplier(p)*(1+jitter)));
  return Math.max(.01,roundMarketPrice(base*multiplier));
}
function marketPriceFields(p:any,i:any,cycle:number){
  const book=basePrice(i);
  const display=cyclePrice(p,i,cycle);
  if(book===null||display===null){
    return {book_price:book,asking_price:display,checkout_unit_price:book,checkout_mode:'standard',checkout_label:'BUY'};
  }
  const epsilon=Math.max(.01,book*.001);
  const below=display<book-epsilon;
  const above=display>book+epsilon;
  return {
    book_price:book,
    asking_price:display,
    checkout_unit_price:book,
    checkout_mode:below?'plus_tax':above?'discount':'standard',
    checkout_label:below?'BUY + TAX':above?'BUY WITH DISCOUNT':'BUY'
  };
}
function stockCondition(p:any,i:any,cycle:number,classMap?:Map<string,any>){
  if(classMap&&quantityClass(i,classMap)==='continuous')return 'not_applicable';
  const options=matchRule(p)?.allowed_conditions;
  if(!Array.isArray(options)||!options.length)return 'new';
  return options[stableIndex('condition|'+cycle+'|'+p.entity_id+'|'+i.id,options.length)];
}
function localOfferings(p:any){
  const sourceRows=Array.isArray(p?.data?.local_offerings)?p.data.local_offerings:[];
  const inferredRows=Array.isArray(p?.data?.stock_curation?.inferred_local_offerings)
    ?p.data.stock_curation.inferred_local_offerings:[];
  const rows=[
    ...sourceRows.map((row:any)=>({...row,_provenance:'source-backed',_inferred:false})),
    ...inferredRows.map((row:any)=>({...row,_provenance:String(row?.provenance||'Vend-R inferred'),_inferred:true}))
  ];
  return rows.map((row:any,idx:number)=>({
    item_id:String(row?.id||((row?._inferred?'INFERRED-':'LOCAL-')+String(p?.entity_id||'SHOP')+'-'+idx)),
    name:String(row?.name||'Local speciality'),
    description:String(row?.description||''),
    primary_department:'local-speciality',
    relation_key:'local:'+String(p?.entity_id||'shop'),
    quantity:null,
    quantity_label:String(row?.quantity_label||'Available'),
    asking_price:Number.isFinite(Number(row?.price_eb))?Number(row.price_eb):null,
    price_label:String(row?.price_label||'Price varies'),
    condition:null,visibility:'public',status:'in_stock',assortment_role:row?._inferred?'curated':'speciality',
    price_tier:'Local',availability_band:'local',
    availability_label:String(row?.availability_label||(row?._inferred?'Vend-R inferred house stock':'Local speciality')),
    availability_rank:0,source_ref:String(row?.source_ref||p?.source_ref||''),
    offering_type:String(row?.offering_type||'speciality_good'),
    provenance:String(row?._provenance||'source-backed'),
    curation_source:row?._inferred?String(row?._provenance||'Vend-R inferred'):null,
    is_inferred:Boolean(row?._inferred),is_local:true,
    stock_cycle:null,observation_generation:null,last_change:null
  }));
}
function localOnlyProfile(p:any){
  return String(matchRule(p)?.strategy||'').toLowerCase()==='local_only';
}

const AMMO_WEAPON_SUBCATEGORIES=new Set([
  'Medium Pistols','Heavy Pistols','Very Heavy Pistols','SMG','Heavy SMG',
  'Shotguns','Assault Rifles','Sniper Rifles','Machine Guns',
  'Bows and Crossbows','Grenade Launchers','Rocket Launchers'
]);
const FIREARM_SUBCATEGORIES=new Set([
  'Medium Pistols','Heavy Pistols','Very Heavy Pistols','SMG','Heavy SMG',
  'Shotguns','Assault Rifles','Sniper Rifles','Machine Guns',
  'Grenade Launchers','Rocket Launchers'
]);
const VEHICLE_SUBCATEGORIES=new Set([
  'Ground Vehicle Types','Ground Vehicles','Air Vehicle Types','Air Vehicles',
  'Sea Vehicle Types','Sea Vehicles','Unique Vehicles'
]);
const PROGRAM_SUBCATEGORIES=new Set([
  'Attacker Programs','Defender Programs','Booster Programs','Black ICE'
]);
const GENERIC_AMMO_PRIORITY=[
  'Basic','Armor-Piercing','Incendiary','Smart','Tracer','Rubber','Expansive',
  'EMP','Explosive','Smoke','Teargas','Sleep','Poison','Biotoxin'
];

function sourceSubcategory(i:any,classMap:Map<string,any>){
  return String(classification(i,classMap)?.source_subcategory||'');
}
function weaponSupportFamily(sub:string){
  if(['Medium Pistols','Heavy Pistols','Very Heavy Pistols','SMG','Heavy SMG'].includes(sub))return 'handgun / SMG';
  if(['Assault Rifles','Sniper Rifles','Machine Guns'].includes(sub))return 'rifle / machine gun';
  if(sub==='Shotguns')return 'shotgun';
  if(sub==='Bows and Crossbows')return 'bow / crossbow';
  if(sub==='Grenade Launchers')return 'grenade launcher';
  if(sub==='Rocket Launchers')return 'rocket launcher';
  return null;
}
function complementCandidateOrder(item:any,kind:string,classMap:Map<string,any>,seed:string){
  const name=displayName(item);
  let priority=50;
  if(kind==='weapon-ammo'){
    const idx=GENERIC_AMMO_PRIORITY.indexOf(name);
    priority=idx>=0?idx:30;
    // Named/model-specific ammunition is useful when matched deliberately, but
    // should not crowd generic ammunition out of every ordinary gun shop.
    if(/\bammo\b/i.test(name)&&idx<0)priority+=20;
  }else{
    priority=availabilityInfo(item).rank*10;
  }
  return priority*1000000+stableIndex(seed+'|'+String(item.id),1000000);
}
function complementAssortment(
  p:any,chosen:any[],all:any[],classMap:Map<string,any>,mfrMap:Map<string,string[]>,
  plan:any,generation:number
){
  const out=chosen.map((x:any)=>({...x}));
  const used=new Set(out.map((x:any)=>String(x.item.id)));
  const seed='complement|'+String(p.entity_id)+'|'+generation;
  const supportKeys=new Set<string>();

  function selectedCount(matcher:(item:any)=>boolean){
    return out.filter((x:any)=>matcher(x.item)).length;
  }
  function removeOneForSupport(){
    const roleRank:any={occasional:0,regular:1,core:2,support:3};
    const candidates=out.map((x:any,i:number)=>({x,i}))
      .filter((v:any)=>!v.x.support_reason)
      .sort((a:any,b:any)=>
        (roleRank[String(a.x.role||'regular')]??1)-(roleRank[String(b.x.role||'regular')]??1) ||
        Number(a.x.fit||0)-Number(b.x.fit||0) ||
        stableIndex(seed+'|victim|'+String(a.x.item.id),2147483647)-
        stableIndex(seed+'|victim|'+String(b.x.item.id),2147483647)
      );
    const victim=candidates[0];
    if(!victim)return false;
    used.delete(String(victim.x.item.id));
    out.splice(victim.i,1);
    return true;
  }
  function ensureSupport(opts:any){
    const existing=selectedCount(opts.matcher);
    let need=Math.max(0,Number(opts.count||0)-existing);
    if(!need)return;
    const candidates=all
      .filter((item:any)=>!used.has(String(item.id))&&opts.matcher(item))
      .sort((a:any,b:any)=>
        complementCandidateOrder(a,opts.kind,classMap,seed)-
        complementCandidateOrder(b,opts.kind,classMap,seed)
      );
    for(const item of candidates){
      if(need<=0)break;
      if(out.length>=Number(plan.total||0)&&!removeOneForSupport())break;
      const normalFit=score(p,item,classMap,mfrMap);
      out.push({
        item,
        fit:normalFit===null?85:normalFit,
        role:'support',
        support_reason:opts.reason,
        support_key:opts.kind,
        compatibility_label:opts.compatibility_label||null
      });
      used.add(String(item.id));
      supportKeys.add(String(opts.kind));
      need--;
    }
  }

  const ammoWeapons=out.filter((x:any)=>AMMO_WEAPON_SUBCATEGORIES.has(sourceSubcategory(x.item,classMap)));
  if(ammoWeapons.length){
    const families=[...new Set(ammoWeapons.map((x:any)=>weaponSupportFamily(sourceSubcategory(x.item,classMap))).filter(Boolean))];
    const isDedicated=String(p.primary_archetype||'')==='weapons-dealer';
    const ammoTarget=Math.min(5,Math.max(isDedicated?2:1,Math.ceil(ammoWeapons.length/(isDedicated?4:6))));
    ensureSupport({
      kind:'weapon-ammo',
      reason:'support stock for weapons currently sold here',
      compatibility_label:families.length?('Weapon support · '+families.join(', ')):'Weapon support stock',
      count:ammoTarget,
      matcher:(item:any)=>sourceSubcategory(item,classMap)==='Ammunition'
    });

    const firearms=ammoWeapons.filter((x:any)=>FIREARM_SUBCATEGORIES.has(sourceSubcategory(x.item,classMap)));
    const attachmentTarget=isDedicated
      ?Math.min(3,Math.max(1,Math.ceil(firearms.length/7)))
      :(firearms.length>=4?1:0);
    if(attachmentTarget){
      ensureSupport({
        kind:'weapon-attachments',
        reason:'accessories for weapons currently sold here',
        compatibility_label:'For stocked firearms',
        count:attachmentTarget,
        matcher:(item:any)=>sourceSubcategory(item,classMap)==='Weapon Attachments'
      });
    }
  }

  const decks=out.filter((x:any)=>sourceSubcategory(x.item,classMap)==='Cyberdecks');
  if(decks.length){
    ensureSupport({
      kind:'cyberdeck-hardware',
      reason:'hardware for cyberdecks currently sold here',
      compatibility_label:'For stocked cyberdecks',
      count:1,
      matcher:(item:any)=>sourceSubcategory(item,classMap)==='Cyberdeck Hardware'
    });
    ensureSupport({
      kind:'cyberdeck-programs',
      reason:'programs for cyberdecks currently sold here',
      compatibility_label:'For stocked cyberdecks',
      count:2,
      matcher:(item:any)=>PROGRAM_SUBCATEGORIES.has(sourceSubcategory(item,classMap))
    });
  }

  const vehicles=out.filter((x:any)=>VEHICLE_SUBCATEGORIES.has(sourceSubcategory(x.item,classMap)));
  if(vehicles.length&&String(p.primary_archetype||'')==='vehicle-dealer'){
    ensureSupport({
      kind:'vehicle-upgrades',
      reason:'upgrades for vehicles currently sold here',
      compatibility_label:'For stocked vehicles',
      count:1,
      matcher:(item:any)=>sourceSubcategory(item,classMap)==='Vehicle Upgrades'
    });
  }

  const cyberlimbs=out.filter((x:any)=>sourceSubcategory(x.item,classMap)==='Cyberlimbs');
  if(cyberlimbs.length&&String(p.primary_archetype||'')==='cyberware-clinic'){
    ensureSupport({
      kind:'cyberware-enhancements',
      reason:'enhancements for cyberlimbs currently sold here',
      compatibility_label:'For stocked cyberlimbs',
      count:1,
      matcher:(item:any)=>sourceSubcategory(item,classMap)==='Cyberware Enhancements'
    });
  }

  return out;
}

function stockCuration(p:any){return p?.data?.stock_curation||{}}
function curationTargetMatch(p:any,i:any,classMap:Map<string,any>,mode:'boost'|'refresh'){
  const c=stockCuration(p);
  const sub=sourceSubcategory(i,classMap),dep=department(i,classMap);
  const subs=Array.isArray(c?.[mode+'_subcategories'])?c[mode+'_subcategories']:[];
  const deps=Array.isArray(c?.[mode+'_departments'])?c[mode+'_departments']:[];
  const subHit=subs.includes(sub),depHit=Boolean(dep&&deps.includes(dep));
  if(subs.length)return subHit;
  return depHit;
}
function curationFit(p:any,i:any,classMap:Map<string,any>,mfrMap:Map<string,string[]>,mode:'boost'|'refresh'){
  const c0=stockCuration(p);
  if(String(c0.refresh_mode||'catalog')==='local')return null;
  if(!curationTargetMatch(p,i,classMap,mode))return null;
  const rule=matchRule(p)||{};
  if(rule.strategy==='no_catalog_stock'||rule.strategy==='local_only')return null;
  const hardGate=ruleAllows(p,i,classMap,mfrMap);
  if(!hardGate.allow)return null;
  const d=department(i,classMap),sub=sourceSubcategory(i,classMap),rel=relationKey(i,classMap);
  const itemName=String(i?.display_name||i?.name||'').toLowerCase();
  if((rule.exclude_departments||[]).includes(d))return null;
  if((rule.excluded_relation_prefixes||[]).some((x:string)=>rel.startsWith(String(x).toLowerCase())))return null;
  if((rule.excluded_name_terms||[]).some((x:string)=>itemName.includes(String(x).toLowerCase())))return null;
  if(rule.strategy==='tiered'&&rule.public_subcategories?.length&&!rule.public_subcategories.includes(sub))return null;
  const max=Number(rule.max_base_price_eb??p.max_base_price_eb),price=basePrice(i);
  if(Number.isFinite(max)&&max>0&&price!==null&&price>max)return null;
  const itemMfrs=mfrMap.get(String(i.id))||[],required=rule.required_manufacturers||[];
  if(required.length){
    const requiredMatch=itemMfrs.some(x=>required.includes(x));
    if(!requiredMatch&&itemMfrs.length)return null;
    if(!requiredMatch&&!itemMfrs.length&&rule.allow_unbranded===false)return null;
  }
  const c=stockCuration(p),subs=Array.isArray(c?.[mode+'_subcategories'])?c[mode+'_subcategories']:[];
  let fit=mode==='boost'?88:70;
  if(subs.includes(sub))fit+=18;
  if(d&&parts(p.primary_departments).includes(d))fit+=12;
  if(d&&parts(p.secondary_departments).includes(d))fit+=5;
  fit+=availabilityAdjustment(p,i);
  return fit;
}
function curatedBoostAssortment(p:any,chosen:any[],all:any[],classMap:Map<string,any>,mfrMap:Map<string,string[]>,generation:number){
  const c=stockCuration(p),target=Math.max(0,Math.floor(Number(c.boost_count)||0));
  const pins=Array.isArray(c.pinned_item_ids)?c.pinned_item_ids.map(String):[];
  if(!target||!pins.length)return chosen;
  const out=chosen.map((x:any)=>({...x})),used=new Set(out.map((x:any)=>String(x.item.id)));
  const itemById=new Map(all.map((item:any)=>[String(item.id),item]));
  let added=0;
  for(const id of pins){
    if(added>=target)break;
    if(used.has(id))continue;
    const item=itemById.get(id);if(!item)continue;
    const normal=score(p,item,classMap,mfrMap);
    out.push({
      item,fit:normal===null?96:Math.max(96,normal),role:'curated',
      curation_reason:'curated shop staple',
      curation_source:String(c.source||'Vend-R inferred')
    });
    used.add(id);added++;
  }
  return out;
}
function stockRowFromChoice(p:any,x:any,classMap:Map<string,any>,generation:number){
  const qty=cycleQuantity(p,x.item,classMap,x.role,generation);
  return {
    item_id:String(x.item.id),name:displayName(x.item),
    quantity:qty,target_quantity:qty,quantity_profile:quantityClass(x.item,classMap),
    condition:stockCondition(p,x.item,generation,classMap),...marketPriceFields(p,x.item,generation),
    visibility:'public',status:'in_stock',assortment_role:x.role,
    primary_department:department(x.item,classMap),source_subcategory:sourceSubcategory(x.item,classMap),
    relation_key:relationKey(x.item,classMap),price_tier:availabilityInfo(x.item).tier,
    availability_band:availabilityInfo(x.item).key,availability_label:availabilityInfo(x.item).label,
    availability_rank:availabilityInfo(x.item).rank,fit_score:x.fit,
    support_reason:x.support_reason||null,support_key:x.support_key||null,
    compatibility_label:x.compatibility_label||null,
    curation_reason:x.curation_reason||null,curation_source:x.curation_source||null,
    stock_cycle:generation,observation_generation:generation,last_change:null
  };
}
function stockFor(p:any,all:any[],classMap:Map<string,any>,mfrMap:Map<string,string[]>,stockGeneration=0){
  if(!['DIRECT_SELLER','EVENT_MARKET','HYBRID_DIRECT_EVENT'].includes(String(p.stock_mode||''))) return [];
  if(localOnlyProfile(p))return [];
  if(String(stockCuration(p).refresh_mode||'catalog')==='local')return [];
  const generation=Math.max(0,Math.floor(Number(stockGeneration)||0)),plan=assortmentPlan(p);
  const ranked=all.map((item:any)=>({item,fit:score(p,item,classMap,mfrMap)})).filter((x:any)=>x.fit!==null);
  const baseChosen=selectAssortment(p,ranked,plan,classMap,generation);
  const supported=complementAssortment(p,baseChosen,all,classMap,mfrMap,plan,generation);
  const chosen=curatedBoostAssortment(p,supported,all,classMap,mfrMap,generation);
  return chosen.map((x:any)=>stockRowFromChoice(p,x,classMap,generation));
}
function refreshCandidatePool(p:any,all:any[],classMap:Map<string,any>,mfrMap:Map<string,string[]>,generation:number){
  const plan=assortmentPlan(p),c=stockCuration(p),shelf=stockFor(p,all,classMap,mfrMap,generation);
  if(String(c.refresh_mode||'catalog')==='local')return shelf;
  const factor=Math.max(2,Number(c.refresh_pool_factor)||5);
  const cap=Math.max(shelf.length,Math.round(Number(plan.total||shelf.length||1)*factor));
  const profile=String(c.refresh_profile||'balanced');
  const jitter=profile==='volatile'?65:profile==='specialist'?32:45;
  const seed='refresh-pool|'+String(p.entity_id)+'|'+generation;
  const ranked=all.map((item:any)=>{
    const normal=score(p,item,classMap,mfrMap),curated=curationFit(p,item,classMap,mfrMap,'refresh');
    if(normal===null&&curated===null)return null;
    return {item,fit:Math.max(normal===null?-999:normal,curated===null?-999:curated)};
  }).filter(Boolean).sort((a:any,b:any)=>{
    const aj=(stableIndex(seed+'|'+a.item.id,2001)-1000)/1000*jitter;
    const bj=(stableIndex(seed+'|'+b.item.id,2001)-1000)/1000*jitter;
    return (Number(b.fit)+bj)-(Number(a.fit)+aj)||String(a.item.id).localeCompare(String(b.item.id));
  });
  const byId=new Map<string,any>();
  for(const row of shelf)byId.set(String(row.item_id),row);
  const coreLimit=Math.max(8,Number(plan.core||0)*2);
  const regularLimit=Math.max(16,Number(plan.regular||0)*4);
  let addedCore=0,addedRegular=0;
  for(const x of ranked){
    if(byId.size>=cap)break;
    const id=String(x.item.id);if(byId.has(id))continue;
    let role='occasional';
    if(addedCore<coreLimit){role='core';addedCore++}
    else if(addedRegular<regularLimit){role='regular';addedRegular++}
    const row=stockRowFromChoice(p,{...x,role,curation_reason:curationFit(p,x.item,classMap,mfrMap,'refresh')!==null?'refresh candidate':null,curation_source:curationFit(p,x.item,classMap,mfrMap,'refresh')!==null?String(c.source||'Vend-R inferred'):null},classMap,generation);
    byId.set(id,row);
  }
  return [...byId.values()];
}
const LAZY_STOCK_VERSION='lazy-1.6.2-explicit-staples';
const ENTITY_REDIRECTS=new Map<string,string>([
  ['NC2045-OUT-RANCHO-CORONADO-290-FUEL-STATION','NC2045-OUT-OUTSKIRTS-296-FUEL-STATION']
]);
function canonicalEntityId(id:string){
  return ENTITY_REDIRECTS.get(String(id||''))||String(id||'');
}
function turnoverChance(p:any){
  const t=String(lifecycle(p)?.turnover||'steady');
  const m:any={fast:.045,steady:.030,irregular:.040,slow:.015,volatile:.060,weekly:.035};
  return m[t]??.030;
}
function visibleStock(rows:any[]){
  return (rows||[]).filter((row:any)=>row.quantity==null||Number(row.quantity)>0);
}
function decorateStockPrices(p:any,rows:any[],all:any[],generation=0){
  const itemById=new Map(all.map((item:any)=>[String(item.id),item]));
  return (rows||[]).map((row:any)=>{
    const item=itemById.get(String(row.item_id));
    if(!item)return row;
    const cycle=Number(row.stock_cycle??row.observation_generation??generation??0)||0;
    return {...row,name:displayName(item),...marketPriceFields(p,item,cycle)};
  });
}
function initialSnapshot(p:any,all:any[],classMap:Map<string,any>,mfrMap:Map<string,string[]>){
  return stockFor(p,all,classMap,mfrMap,0).map((row:any)=>({
    ...row,
    target_quantity:row.quantity,
    observation_generation:0,
    stock_cycle:0,
    last_change:null
  }));
}
function transitionObservedStock(p:any,snapshot:any[],all:any[],classMap:Map<string,any>,mfrMap:Map<string,string[]>,generation:number,stateAt:string,nowMs=Date.now()){
  const then=Date.parse(stateAt||'');
  if(!Number.isFinite(then)||!snapshot.length)return {changed:false,generation,state_at:stateAt,snapshot,mutations:0,elapsed_days:0};
  const elapsedDays=Math.max(0,(nowMs-then)/86400000);
  if(elapsedDays<=0)return {changed:false,generation,state_at:stateAt,snapshot,mutations:0,elapsed_days:0};

  // One bounded catch-up transition. This approximates accumulated commercial
  // movement without replaying the days between observations.
  const fraction=1-Math.exp(-turnoverChance(p)*elapsedDays);
  const expected=snapshot.length*fraction;
  let mutations=Math.floor(expected);
  const remainder=expected-mutations;
  const seedBase=LAZY_STOCK_VERSION+'|'+p.entity_id+'|'+generation+'|'+stateAt;
  if(stableIndex(seedBase+'|round',10000)<Math.round(remainder*10000))mutations++;
  mutations=Math.min(snapshot.length,mutations);
  if(mutations<1)return {changed:false,generation,state_at:stateAt,snapshot,mutations:0,elapsed_days:elapsedDays};

  const nextGeneration=generation+1;
  const candidates=refreshCandidatePool(p,all,classMap,mfrMap,nextGeneration);
  const rows=snapshot.map((r:any)=>({...r,last_change:null}));
  const used=new Set(rows.map((r:any)=>String(r.item_id)));
  const order=rows.map((_:any,i:number)=>i).sort((a:number,b:number)=>
    stableIndex(seedBase+'|pick|'+rows[a].item_id,2147483647)-
    stableIndex(seedBase+'|pick|'+rows[b].item_id,2147483647)
  );

  function replacementChance(role:string){
    if(role==='occasional')return Math.min(.95,.15+elapsedDays*.04);
    if(role==='regular')return Math.min(.80,elapsedDays*.02);
    if(role==='core')return elapsedDays<90?0:Math.min(.20,(elapsedDays-90)*.0025);
    return Math.min(.55,elapsedDays*.015);
  }
  function replacementFor(row:any,idx:number){
    const role=String(row.assortment_role||'regular'),dept=String(row.primary_department||'');
    const free=candidates.filter((x:any)=>!used.has(String(x.item_id)));
    if(!free.length)return null;
    const sameRole=free.filter((x:any)=>String(x.assortment_role||'regular')===role);
    const sameDept=free.filter((x:any)=>String(x.primary_department||'')===dept);
    const roll=stableIndex(seedBase+'|replace-band|'+idx+'|'+row.item_id,100);
    let pool:any[]=free;
    if(role==='core'&&sameRole.length)pool=roll<85?sameRole:(sameDept.length?sameDept:free);
    else if((role==='support'||role==='curated')&&sameDept.length)pool=roll<70?sameDept:(sameRole.length?sameRole:free);
    else if(sameRole.length)pool=roll<55?sameRole:(sameDept.length&&roll<82?sameDept:free);
    else if(sameDept.length&&roll<70)pool=sameDept;
    return pool[stableIndex(seedBase+'|replace|'+idx+'|'+row.item_id,pool.length)];
  }

  for(const idx of order.slice(0,mutations)){
    const row=rows[idx], role=String(row.assortment_role||'regular');
    const replaceRoll=stableIndex(seedBase+'|replace-roll|'+row.item_id,10000)/10000;
    if(replaceRoll<replacementChance(role)){
      const candidate=replacementFor(row,idx);
      if(candidate){
        used.delete(String(row.item_id));used.add(String(candidate.item_id));
        rows[idx]={
          ...candidate,
          target_quantity:candidate.quantity,
          observation_generation:nextGeneration,
          stock_cycle:nextGeneration,
          last_change:'new arrival'
        };
        continue;
      }
    }

    if(row.quantity==null){
      rows[idx]={...row,observation_generation:nextGeneration,stock_cycle:nextGeneration};
      continue;
    }

    let qty=Math.max(0,Number(row.quantity)||0);
    const target=Math.max(1,Number(row.target_quantity??row.quantity??1));
    const action=stableIndex(seedBase+'|action|'+row.item_id,1000);
    let change:string|null=null;

    if(action<600){
      const max=Math.max(1,Math.round(Math.max(qty,target)*.30));
      const amount=1+stableIndex(seedBase+'|sale|'+row.item_id,max);
      qty=Math.max(0,qty-amount);
      change=qty===0?'sold out':'selling down';
    }else if(action<850){
      const max=Math.max(1,Math.round(target*.25));
      const amount=1+stableIndex(seedBase+'|delivery|'+row.item_id,max);
      qty=Math.min(Math.round(target*1.5),qty+amount);
      change='fresh delivery';
    }else if(action<930){
      qty=0;change='sold out';
    }else{
      const room=Math.max(1,target-qty);
      const amount=1+stableIndex(seedBase+'|restock|'+row.item_id,room);
      qty=Math.min(target,qty+amount);
      change='restocked';
    }
    rows[idx]={
      ...row,
      quantity:qty,
      status:qty>0?'in_stock':'sold',
      observation_generation:nextGeneration,
      stock_cycle:nextGeneration,
      last_change:change
    };
  }

  return {
    changed:true,
    generation:nextGeneration,
    state_at:new Date(nowMs).toISOString(),
    snapshot:rows,
    mutations,
    elapsed_days:elapsedDays
  };
}
async function observationForShop(entityId:string,worldKey='public-2045'){
  return await db('vendr_stock_observations',
    'select=world_key,entity_id,generation,state_at,snapshot,model_version,updated_at'+
    '&world_key=eq.'+encodeURIComponent(worldKey)+
    '&entity_id=eq.'+encodeURIComponent(entityId)
  );
}
async function saveObservation(worldKey:string,p:any,generation:number,stateAt:string,snapshot:any[]){
  const rows=await dbUpsert('vendr_stock_observations',{
    world_key:worldKey,
    entity_id:String(p.entity_id),
    generation,
    state_at:stateAt,
    snapshot,
    model_version:LAZY_STOCK_VERSION,
    updated_at:new Date().toISOString()
  },'world_key,entity_id');
  return rows[0]||null;
}
async function resolveObservedStock(p:any,all:any[],classMap:Map<string,any>,mfrMap:Map<string,string[]>,worldKey='public-2045'){
  if(localOnlyProfile(p)){
    return {
      snapshot:[],visible:[],generation:0,state_at:null,
      first_observation:false,model_migrated:false,changed:false,
      mutations:0,elapsed_days:0
    };
  }
  const obsRows=await observationForShop(String(p.entity_id),worldKey);
  const obs=obsRows[0]||null;
  const nowMs=Date.now();

  if(!obs||String(obs.model_version||'')!==LAZY_STOCK_VERSION){
    const snapshot=initialSnapshot(p,all,classMap,mfrMap);
    const stateAt=new Date(nowMs).toISOString();
    await saveObservation(worldKey,p,0,stateAt,snapshot);
    const priced=decorateStockPrices(p,snapshot,all,0);
    return {
      snapshot:priced,visible:visibleStock(priced),generation:0,state_at:stateAt,
      first_observation:!obs,model_migrated:Boolean(obs),changed:Boolean(obs),
      mutations:0,elapsed_days:0
    };
  }

  const snapshot=Array.isArray(obs.snapshot)?obs.snapshot:[];
  const result=transitionObservedStock(p,snapshot,all,classMap,mfrMap,Number(obs.generation||0),String(obs.state_at||obs.updated_at||new Date(nowMs).toISOString()),nowMs);
  if(result.changed)await saveObservation(worldKey,p,result.generation,result.state_at,result.snapshot);
  const priced=decorateStockPrices(p,result.snapshot,all,result.generation);
  return {...result,snapshot:priced,visible:visibleStock(priced),first_observation:false};
}

async function sourcesApi(u:URL){
  const active=requestedSourceCodes(u);
  const [all,sourceMap,books,profileRows]=await Promise.all([
    catalogue(),itemSourceMap(),sourceBooks(),
    db('vendr_stock_profiles','select=*&order=name.asc')
  ]);
  const profiles=profileRows.filter(isVendrVisibleProfile);
  const countMap=new Map<string,Set<string>>();
  for(const [itemId,links] of sourceMap.entries()){
    for(const link of links){
      const code=String(link.code||'');
      if(!code)continue;
      const set=countMap.get(code)||new Set<string>();
      set.add(String(itemId)); countMap.set(code,set);
    }
  }
  const localEntries=new Map<string,Set<string>>();
  for(const p of profiles){
    for(const offering of localOfferings(p)){
      const code=offeringSourceCode(offering,books);
      const set=localEntries.get(code)||new Set<string>();
      set.add(String(offering.item_id)); localEntries.set(code,set);
    }
  }
  const profileCounts=new Map<string,number>();
  for(const p of profiles){
    const code=sourceCodeFromRef(p.source_ref,books);
    if(!code)continue;
    profileCounts.set(code,(profileCounts.get(code)||0)+1);
  }
  const definitions=[
    ...books.map((row:any)=>sourceMeta(row)),
    {...VENDR_SOURCE}
  ].map((row:any)=>{
    const ids=new Set<string>([...(countMap.get(String(row.code))||[]),...(localEntries.get(String(row.code))||[])]);
    return {...row,item_count:ids.size,profile_count:profileCounts.get(String(row.code))||0};
  });
  const visibleIds=new Set<string>();
  for(const item of all)if(itemAllowed(item.id,sourceMap,active))visibleIds.add(String(item.id));
  for(const [code,ids] of localEntries.entries()){
    if(active===null||active.has(code))for(const id of ids)visibleIds.add(id);
  }
  const allCodes=definitions.map((row:any)=>String(row.code));
  const activeCodes=active===null?allCodes:allCodes.filter(code=>active.has(code));
  const visibleProfiles=profiles.filter((p:any)=>profileAllowed(p,active,books)).length;
  return out({
    sources:definitions,
    active_source_codes:activeCodes,
    visible_item_count:visibleIds.size,
    visible_profile_count:visibleProfiles,
    total_catalogue_items:all.length,
    total_source_count:definitions.length
  });
}

async function search(u:URL){
  const q=(u.searchParams.get('q')||'').trim();
  const activeId=u.searchParams.get('item_id');
  const suggestOnly=u.searchParams.get('suggest')==='1';
  if(!q) return out({query:q,active_item_id:null,items:[],offers:[],total_matches:0});

  const activeSources=requestedSourceCodes(u);
  const [all,classMap,descMap,profileRows,sourceMap,books]=await Promise.all([
    catalogue(),classifications(),descriptions(),
    db('vendr_stock_profiles','select=*&order=name.asc'),
    itemSourceMap(),sourceBooks()
  ]);
  const visibleAll=all.filter((i:any)=>itemAllowed(i.id,sourceMap,activeSources));
  const profiles=profileRows.filter((p:any)=>isVendrVisibleProfile(p)&&profileAllowed(p,activeSources,books));
  const f=q.toLowerCase();

  const direct=visibleAll.filter((i:any)=>(String(i.name||'')+' '+displayName(i)).toLowerCase().includes(f));
  const qnorm=f.replace(/[^a-z0-9]+/g,' ').trim();
  const qterms=qnorm.split(/\s+/).filter(Boolean).map(t=>t==='ammo'?'ammunition':t);
  const exactDirect=direct.filter((i:any)=>[String(i.name||''),displayName(i)].some(n=>n.trim().toLowerCase()===f));
  const anchorDirect=direct.filter((i:any)=>{
    const cls=classification(i,classMap)||{};
    const label=(String(cls.source_category||'')+' '+String(cls.source_subcategory||'')).toLowerCase().replace(/[^a-z0-9]+/g,' ');
    return qterms.length&&qterms.every(t=>label.includes(t));
  });
  let relationAnchors=exactDirect.length?exactDirect:anchorDirect;
  if(!relationAnchors.length&&direct.length){
    const counts=new Map<string,number>();
    for(const i of direct){
      const d=department(i,classMap)||'other';
      counts.set(d,(counts.get(d)||0)+1);
    }
    const dominant=[...counts.entries()].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0]))[0]?.[0];
    relationAnchors=direct.filter((i:any)=>(department(i,classMap)||'other')===dominant);
  }
  const relatedKeys=new Set(relationAnchors.map((i:any)=>relationKey(i,classMap)).filter(Boolean));

  const matches=visibleAll.filter((i:any)=>{
    const name=(String(i.name||'')+' '+displayName(i)).toLowerCase();
    if(exactDirect.length) return relatedKeys.has(relationKey(i,classMap));
    return name.includes(f) || relatedKeys.has(relationKey(i,classMap));
  }).sort((a:any,b:any)=>{
    const an=displayName(a),bn=displayName(b),af=an.toLowerCase(),bf=bn.toLowerCase();
    const ad=af.includes(f),bd=bf.includes(f);
    const ar=af===f?0:af.startsWith(f)?1:ad?2:3;
    const br=bf===f?0:bf.startsWith(f)?1:bd?2:3;
    return ar-br||an.length-bn.length||an.localeCompare(bn);
  });

  const catalogItemRows=matches.map((i:any)=>({
    item_id:i.id,
    name:displayName(i),
    catalog_name:i.name,
    context_qualifier:i.context_qualifier||null,
    description:descMap.get(String(i.id))||null,
    primary_department:department(i,classMap),
    relation_key:relationKey(i,classMap),
    book_price:basePrice(i),
    price_tier:availabilityInfo(i).tier,
    availability_band:availabilityInfo(i).key,
    availability_label:availabilityInfo(i).label,
    availability_rank:availabilityInfo(i).rank,
    sources:sourceRowsForItem(i.id,sourceMap,books)
  }));

  const localMatches:any[]=[];
  for(const p of profiles){
    for(const offering of localOfferings(p)){
      if(!offeringAllowed(offering,activeSources,books))continue;
      const hay=[offering.name,offering.description,p.name,p.data?.short_description]
        .filter(Boolean).join(' ').toLowerCase();
      if(hay.includes(f)) localMatches.push({profile:p,offering});
    }
  }
  localMatches.sort((a:any,b:any)=>{
    const an=String(a.offering.name||''),bn=String(b.offering.name||'');
    const af=an.toLowerCase(),bf=bn.toLowerCase();
    const ar=af===f?0:af.startsWith(f)?1:af.includes(f)?2:3;
    const br=bf===f?0:bf.startsWith(f)?1:bf.includes(f)?2:3;
    return ar-br||an.length-bn.length||an.localeCompare(bn);
  });
  const localItemRows=localMatches.map(({profile:p,offering}:any)=>({
    item_id:offering.item_id,
    name:offering.name,
    catalog_name:null,
    context_qualifier:p.name,
    description:offering.description||null,
    primary_department:'local-speciality',
    relation_key:offering.relation_key,
    book_price:null,
    price_tier:'Local speciality',
    availability_band:'local',
    availability_label:offering.availability_label||'Available here',
    availability_rank:0,
    source_ref:offering.source_ref||p.source_ref||null,
    sources:localSourceRows(offering,books),
    is_local:true,
    shop_entity_id:p.entity_id,
    shop_name:p.name
  }));
  const itemRows=[...localItemRows,...catalogItemRows];

  if(suggestOnly){
    return out({query:q,active_item_id:null,items:itemRows.slice(0,10),total_matches:itemRows.length,offers:[]});
  }

  const activeCatalog=activeId?matches.find((i:any)=>String(i.id)===activeId):null;
  const activeLocal=activeId?localMatches.find((x:any)=>String(x.offering.item_id)===activeId):null;
  const mfrMap=await manufacturers();
  const [placeRows,observationRows]=await Promise.all([
    db('vendr_places','select=entity_id,parent_name,district,spatial_mode'),
    db('vendr_stock_observations','select=entity_id,generation,state_at,snapshot,model_version&world_key=eq.public-2045')
  ]);
  const placeMap=new Map(placeRows.map((r:any)=>[String(r.entity_id),r]));
  const observationMap=new Map(observationRows.map((r:any)=>[String(r.entity_id),r]));
  const offerItems=activeCatalog?[activeCatalog]:(activeLocal?[]:matches);
  const stockCache=new Map<string,any[]>();
  const offers:any[]=[];

  const localOfferMatches=activeLocal?[activeLocal]:(activeCatalog?[]:localMatches);
  for(const {profile:p,offering} of localOfferMatches){
    const place:any=placeMap.get(String(p.entity_id))||{};
    offers.push({
      kind:'available',item_id:offering.item_id,item_name:offering.name,
      primary_department:'local-speciality',relation_key:offering.relation_key,
      shop_entity_id:p.entity_id,shop_name:p.name,district:place.district||p.district,
      parent_name:place.parent_name||null,spatial_mode:place.spatial_mode||null,
      distance:null,score:999,stock_mode:p.stock_mode,quantity:null,
      quantity_label:offering.quantity_label||'Available',asking_price:offering.asking_price??null,
      price_label:offering.price_label||'Price varies',book_price:null,checkout_unit_price:null,
      checkout_mode:null,checkout_label:null,condition:null,stock_cycle:null,
      price_tier:'Local speciality',availability_band:'local',
      availability_label:offering.availability_label||'Available here',availability_rank:0,is_local:true
    });
  }

  for(const item of offerItems){
    const itemId=String(item.id);
    for(const p of profiles){
      let stock=stockCache.get(String(p.entity_id));
      if(!stock){
        const obs:any=observationMap.get(String(p.entity_id));
        const raw=!localOnlyProfile(p)&&obs&&String(obs.model_version||'')===LAZY_STOCK_VERSION&&Array.isArray(obs.snapshot)
          ?obs.snapshot:initialSnapshot(p,all,classMap,mfrMap);
        stock=visibleStock(decorateStockPrices(p,raw,all,Number(obs?.generation??0)));
        stockCache.set(String(p.entity_id),stock);
      }
      const row=stock.find((r:any)=>String(r.item_id)===itemId);
      const localMode=String(stockCuration(p).refresh_mode||'catalog')==='local';
      const fit=localMode?null:score(p,item,classMap,mfrMap),curatedFit=localMode?null:curationFit(p,item,classMap,mfrMap,'refresh');
      if(fit===null&&curatedFit===null&&!row)continue;
      const effectiveFit=fit===null?(curatedFit??(row?.support_reason?90:70)):Math.max(fit,curatedFit??-999);
      const place=placeMap.get(String(p.entity_id))||{};
      offers.push({
        kind:row?'available':'plausible',item_id:itemId,item_name:displayName(item),
        primary_department:department(item,classMap),relation_key:relationKey(item,classMap),
        shop_entity_id:p.entity_id,shop_name:p.name,district:place.district||p.district,
        parent_name:place.parent_name||null,spatial_mode:place.spatial_mode||null,distance:null,
        score:effectiveFit,stock_mode:p.stock_mode,quantity:row?.quantity??null,
        asking_price:row?.asking_price??null,book_price:row?.book_price??basePrice(item),
        checkout_unit_price:row?.checkout_unit_price??basePrice(item),checkout_mode:row?.checkout_mode??null,
        checkout_label:row?.checkout_label??null,condition:row?.condition??null,stock_cycle:row?.stock_cycle??null,
        support_reason:row?.support_reason??null,support_key:row?.support_key??null,
        compatibility_label:row?.compatibility_label??null,price_tier:row?.price_tier??availabilityInfo(item).tier,
        availability_band:row?.availability_band??availabilityInfo(item).key,
        availability_label:row?.availability_label??availabilityInfo(item).label,
        availability_rank:row?.availability_rank??availabilityInfo(item).rank
      });
    }
  }
  offers.sort((a,b)=>(a.kind!=='available')-(b.kind!=='available')||Number(b.score)-Number(a.score)||String(a.shop_name).localeCompare(String(b.shop_name)));
  return out({
    query:q,
    active_item_id:activeLocal?String(activeLocal.offering.item_id):(activeCatalog?String(activeCatalog.id):null),
    items:itemRows,offers:offers.slice(0,60),total_matches:itemRows.length,
    catalogue_count:visibleAll.length,seller_profile_count:profiles.length,stock_cycle:null
  });
}

async function itemDetail(u:URL){
  const id=String(u.searchParams.get('id')||'').trim();
  if(!id)return out({error:'missing id'},400);

  const activeSources=requestedSourceCodes(u);
  const [all,classMap,mfrMap,descMap,profileRows,placeRows,observationRows,sourceMap,books]=await Promise.all([
    catalogue(),classifications(),manufacturers(),descriptions(),
    db('vendr_stock_profiles','select=*&order=name.asc'),
    db('vendr_places','select=entity_id,parent_name,district,spatial_mode'),
    db('vendr_stock_observations','select=entity_id,generation,state_at,snapshot,model_version&world_key=eq.public-2045'),
    itemSourceMap(),sourceBooks()
  ]);
  const profiles=profileRows.filter((p:any)=>isVendrVisibleProfile(p)&&profileAllowed(p,activeSources,books));
  const placeMap=new Map(placeRows.map((r:any)=>[String(r.entity_id),r]));
  const observationMap=new Map(observationRows.map((r:any)=>[String(r.entity_id),r]));

  let localHit:any=null;
  for(const p of profiles){
    const offering=localOfferings(p).find((x:any)=>String(x.item_id)===id&&offeringAllowed(x,activeSources,books));
    if(offering){localHit={profile:p,offering};break}
  }
  if(localHit){
    const p=localHit.profile, offering=localHit.offering;
    const place:any=placeMap.get(String(p.entity_id))||{};
    const related=localOfferings(p)
      .filter((x:any)=>String(x.item_id)!==id&&offeringAllowed(x,activeSources,books))
      .map((x:any)=>({item_id:x.item_id,name:x.name,description:x.description,price_tier:'Local'}));
    return out({
      item:{
        item_id:offering.item_id,name:offering.name,catalog_name:null,context_qualifier:null,
        description:offering.description||null,primary_department:'local-speciality',
        relation_key:offering.relation_key,
        classification:{source_category:'Local wares',source_subcategory:'Local speciality'},
        manufacturers:[],book_price:null,price_tier:'Local speciality',
        availability_band:'local',availability_label:offering.availability_label||'Available here',
        source_index_page:null,source_ref:offering.source_ref||p.source_ref||null,
        sources:localSourceRows(offering,books),local:true,image:null
      },
      offers:[{
        kind:'available',item_id:offering.item_id,item_name:offering.name,
        primary_department:'local-speciality',relation_key:offering.relation_key,
        shop_entity_id:p.entity_id,shop_name:p.name,district:place.district||p.district,
        parent_name:place.parent_name||null,spatial_mode:place.spatial_mode||null,
        distance:null,score:999,stock_mode:p.stock_mode,quantity:null,
        quantity_label:offering.quantity_label||'Available',asking_price:offering.asking_price??null,
        price_label:offering.price_label||'Price varies',book_price:null,checkout_unit_price:null,
        checkout_mode:null,checkout_label:null,condition:null,stock_cycle:null,price_tier:'Local',
        availability_band:'local',availability_label:offering.availability_label||'Available here',
        availability_rank:0,is_local:true
      }],
      related
    });
  }

  const item=all.find((x:any)=>String(x.id)===id);
  if(!item)return out({error:'item not found'},404);
  if(!itemAllowed(id,sourceMap,activeSources))return out({error:'item excluded by source selection'},404);
  const offers:any[]=[];
  for(const p of profiles){
    const obs:any=observationMap.get(String(p.entity_id));
    const raw=!localOnlyProfile(p)&&obs&&String(obs.model_version||'')===LAZY_STOCK_VERSION&&Array.isArray(obs.snapshot)
      ?obs.snapshot:initialSnapshot(p,all,classMap,mfrMap);
    const stock=visibleStock(decorateStockPrices(p,raw,all,Number(obs?.generation??0)));
    const row=stock.find((r:any)=>String(r.item_id)===id);
    const localMode=String(stockCuration(p).refresh_mode||'catalog')==='local';
    const fit=localMode?null:score(p,item,classMap,mfrMap),curatedFit=localMode?null:curationFit(p,item,classMap,mfrMap,'refresh');
    if(fit===null&&curatedFit===null&&!row)continue;
    const effectiveFit=fit===null?(curatedFit??(row?.support_reason?90:70)):Math.max(fit,curatedFit??-999);
    const place=placeMap.get(String(p.entity_id))||{};
    offers.push({
      kind:row?'available':'plausible',item_id:id,item_name:displayName(item),
      primary_department:department(item,classMap),relation_key:relationKey(item,classMap),
      shop_entity_id:p.entity_id,shop_name:p.name,district:place.district||p.district,
      parent_name:place.parent_name||null,spatial_mode:place.spatial_mode||null,distance:null,
      score:effectiveFit,stock_mode:p.stock_mode,quantity:row?.quantity??null,
      asking_price:row?.asking_price??null,book_price:row?.book_price??basePrice(item),
      checkout_unit_price:row?.checkout_unit_price??basePrice(item),checkout_mode:row?.checkout_mode??null,
      checkout_label:row?.checkout_label??null,condition:row?.condition??null,stock_cycle:row?.stock_cycle??null,
      support_reason:row?.support_reason??null,support_key:row?.support_key??null,
      compatibility_label:row?.compatibility_label??null,price_tier:row?.price_tier??availabilityInfo(item).tier,
      availability_band:row?.availability_band??availabilityInfo(item).key,
      availability_label:row?.availability_label??availabilityInfo(item).label,
      availability_rank:row?.availability_rank??availabilityInfo(item).rank
    });
  }
  offers.sort((a:any,b:any)=>(a.kind!=='available')-(b.kind!=='available')||Number(b.score)-Number(a.score)||String(a.shop_name).localeCompare(String(b.shop_name)));

  const rel=relationKey(item,classMap);
  const related=all
    .filter((x:any)=>String(x.id)!==id&&itemAllowed(x.id,sourceMap,activeSources)&&relationKey(x,classMap)===rel)
    .slice(0,12)
    .map((x:any)=>({
      item_id:String(x.id),name:displayName(x),description:descMap.get(String(x.id))||null,
      price_tier:availabilityInfo(x).tier
    }));
  const cls=classification(item,classMap)||null;
  return out({
    item:{
      item_id:id,name:displayName(item),catalog_name:item.name||null,
      context_qualifier:item.context_qualifier||null,description:descMap.get(id)||null,
      primary_department:department(item,classMap),relation_key:rel,classification:cls,
      manufacturers:mfrMap.get(id)||[],book_price:basePrice(item),price_tier:availabilityInfo(item).tier,
      availability_band:availabilityInfo(item).key,availability_label:availabilityInfo(item).label,
      source_index_page:item.source_index_page??null,sources:sourceRowsForItem(id,sourceMap,books),image:null
    },
    offers:offers.slice(0,80),related
  });
}

async function purchase(req:Request){
  if(req.method!=='POST')return out({error:'POST required'},405);
  const user=await authenticatedUser(req);
  if(!user)return out({error:'Authentication required for stock mutation'},401);

  const body=await req.json().catch(()=>null);
  const entityId=canonicalEntityId(String(body?.entity_id||''));
  const itemId=String(body?.item_id||'');
  if(itemId.startsWith('LOCAL-'))return out({error:'local specialities are not quantity-tracked'},409);
  const quantity=Math.max(1,Math.floor(Number(body?.quantity||1)));
  const worldKey=String(body?.world_key||'public-2045');
  if(!entityId||!itemId||!Number.isFinite(quantity))return out({error:'entity_id, item_id and a positive quantity are required'},400);

  const profiles=await db('vendr_stock_profiles','select=*&entity_id=eq.'+encodeURIComponent(entityId));
  const p=profiles[0];
  if(!p||!isVendrVisibleProfile(p))return out({error:'seller is not listed on Vend-R'},404);
  if(!['DIRECT_SELLER','EVENT_MARKET','HYBRID_DIRECT_EVENT'].includes(String(p.stock_mode||'')))return out({error:'place does not own shelf stock'},409);

  const [all,classMap,mfrMap]=await Promise.all([catalogue(),classifications(),manufacturers()]);
  const resolved=await resolveObservedStock(p,all,classMap,mfrMap,worldKey);
  const currentRow=resolved.snapshot.find((r:any)=>String(r.item_id)===itemId);
  if(!currentRow)return out({error:'item is not in current stock'},409);
  if(currentRow.quantity!=null&&quantity>Number(currentRow.quantity||0))return out({error:'insufficient stock',available:Number(currentRow.quantity||0)},409);

  try{
    return out(await rpc('vendr_apply_snapshot_purchase',{
      p_world_key:worldKey,
      p_entity_id:entityId,
      p_item_id:itemId,
      p_quantity:quantity
    }));
  }catch(e:any){
    if(String(e?.message||'').toLowerCase().includes('insufficient stock'))return out({error:'insufficient stock'},409);
    throw e;
  }
}
async function health(){
  const all=await catalogue(), profiles=await db('vendr_stock_profiles','select=*'), places=await db('vendr_places','select=entity_id');
  const visibleProfiles=profiles.filter(isVendrVisibleProfile);
  return out({
    ok:true,service:'vend-r-supabase',catalog_items:all.length,
    profiles:visibleProfiles.length,commercial_profiles_total:profiles.length,places:places.length,
    visibility_model:'retail_only_v1',read_only:true,stock_model:LAZY_STOCK_VERSION
  });
}
function refreshCandidateStats(p:any,all:any[],classMap:Map<string,any>,mfrMap:Map<string,string[]>,shelfCount:number){
  const plan=assortmentPlan(p),c=stockCuration(p),factor=Math.max(2,Number(c.refresh_pool_factor)||5);
  if(String(c.refresh_mode||'catalog')==='local'){
    const themes=Array.isArray(c.local_refresh_themes)?c.local_refresh_themes:[];
    const capacity=Math.max(localOfferings(p).length,Number(c.local_refresh_capacity)||themes.length);
    return {eligible:capacity,pool_size:capacity,departments:1,subcategories:themes.length,mode:'local'};
  }
  const deps=new Set<string>(),subs=new Set<string>();
  let eligible=0;
  for(const item of all){
    const normal=score(p,item,classMap,mfrMap),curated=curationFit(p,item,classMap,mfrMap,'refresh');
    if(normal===null&&curated===null)continue;
    eligible++;
    deps.add(String(department(item,classMap)||'other'));
    subs.add(String(sourceSubcategory(item,classMap)||'other'));
  }
  const cap=Math.max(shelfCount,Math.round(Number(plan.total||shelfCount||1)*factor));
  return {eligible,pool_size:Math.max(shelfCount,Math.min(eligible,cap)),departments:deps.size,subcategories:subs.size};
}
async function stockAudit(){
  const [all,classMap,mfrMap,profiles]=await Promise.all([
    catalogue(),classifications(),manufacturers(),db('vendr_stock_profiles','select=*&order=name.asc')
  ]);
  const owners=profiles.filter((p:any)=>isVendrVisibleProfile(p)&&['DIRECT_SELLER','EVENT_MARKET','HYBRID_DIRECT_EVENT'].includes(String(p.stock_mode||'')));
  const rows=owners.map((p:any)=>{
    const plan=assortmentPlan(p);
    const stock=initialSnapshot(p,all,classMap,mfrMap);
    const refreshStats=refreshCandidateStats(p,all,classMap,mfrMap,stock.length);
    const deps:any={}, availability:any={}, complements:any={};
    for(const row of stock){
      const d=String(row.primary_department||'other');
      deps[d]=(deps[d]||0)+1;
      const a=String(row.availability_band||'common');
      availability[a]=(availability[a]||0)+1;
      if(row.support_key){
        const k=String(row.support_key);
        complements[k]=(complements[k]||0)+1;
      }
    }
    const ammoWeaponCount=stock.filter((row:any)=>AMMO_WEAPON_SUBCATEGORIES.has(String(row.source_subcategory||''))).length;
    const firearmCount=stock.filter((row:any)=>FIREARM_SUBCATEGORIES.has(String(row.source_subcategory||''))).length;
    const cyberdeckCount=stock.filter((row:any)=>String(row.source_subcategory||'')==='Cyberdecks').length;
    const vehicleCount=stock.filter((row:any)=>VEHICLE_SUBCATEGORIES.has(String(row.source_subcategory||''))).length;
    const cyberdeckHardwareCount=stock.filter((row:any)=>String(row.source_subcategory||'')==='Cyberdeck Hardware').length;
    const cyberdeckProgramCount=stock.filter((row:any)=>PROGRAM_SUBCATEGORIES.has(String(row.source_subcategory||''))).length;
    const vehicleUpgradeCount=stock.filter((row:any)=>String(row.source_subcategory||'')==='Vehicle Upgrades').length;
    return {
      entity_id:p.entity_id,name:p.name,district:p.district,stock_mode:p.stock_mode,
      archetype:p.primary_archetype,planned:plan.total,generated:stock.length,
      local_offerings:localOfferings(p).length,
      inferred_local_offerings:localOfferings(p).filter((row:any)=>row.is_inferred).length,
      effective_lines:stock.length+localOfferings(p).length,
      refresh_mode:String(stockCuration(p).refresh_mode||'catalog'),
      local_refresh_themes:Array.isArray(stockCuration(p).local_refresh_themes)?stockCuration(p).local_refresh_themes.length:0,
      curated_lines:stock.filter((row:any)=>row.curation_reason==='curated shop staple').length,
      curated_names:stock.filter((row:any)=>row.curation_reason==='curated shop staple').map((row:any)=>row.name),
      refresh_candidates:refreshStats.pool_size,
      refresh_eligible:refreshStats.eligible,
      refresh_departments:refreshStats.departments,
      refresh_subcategories:refreshStats.subcategories,
      ammo_weapon_count:ammoWeaponCount,firearm_count:firearmCount,
      cyberdeck_count:cyberdeckCount,vehicle_count:vehicleCount,
      cyberdeck_hardware_count:cyberdeckHardwareCount,cyberdeck_program_count:cyberdeckProgramCount,
      vehicle_upgrade_count:vehicleUpgradeCount,
      availability_context:availabilityContext(p),
      departments:deps,availability,complements
    };
  });
  const catalogueAvailability:any={};
  for(const item of all){
    const a=availabilityInfo(item).key;
    catalogueAvailability[a]=(catalogueAvailability[a]||0)+1;
  }
  const weaponSellers=rows.filter((r:any)=>Number(r.departments?.weapons||0)>0);
  const ammoWeaponSellers=rows.filter((r:any)=>Number(r.ammo_weapon_count||0)>0);
  const firearmSellers=rows.filter((r:any)=>Number(r.firearm_count||0)>0);
  const cyberdeckSellers=rows.filter((r:any)=>Number(r.cyberdeck_count||0)>0);
  const vehicleDealers=rows.filter((r:any)=>String(r.archetype||'')==='vehicle-dealer'&&Number(r.vehicle_count||0)>0);
  return out({
    stock_model:LAZY_STOCK_VERSION,
    coherence:{
      weapon_sellers:weaponSellers.length,
      ammo_using_weapon_sellers:ammoWeaponSellers.length,
      ammo_using_weapon_sellers_without_ammo:ammoWeaponSellers.filter((r:any)=>Number(r.departments?.['ammunition-ordnance']||0)===0).length,
      firearm_sellers_without_parts:firearmSellers.filter((r:any)=>Number(r.departments?.['weapon-parts']||0)===0).length,
      cyberdeck_sellers:cyberdeckSellers.length,
      cyberdeck_sellers_without_hardware:cyberdeckSellers.filter((r:any)=>Number(r.cyberdeck_hardware_count||0)===0).length,
      cyberdeck_sellers_without_programs:cyberdeckSellers.filter((r:any)=>Number(r.cyberdeck_program_count||0)===0).length,
      vehicle_dealers:vehicleDealers.length,
      vehicle_dealers_without_upgrade_support:vehicleDealers.filter((r:any)=>Number(r.vehicle_upgrade_count||0)===0).length
    },
    owners:rows.length,
    zero_count:rows.filter((r:any)=>r.generated===0).length,
    underfilled_count:rows.filter((r:any)=>r.generated>0&&r.generated<Math.max(3,Math.floor(r.planned*.5))).length,
    refresh_pool:{
      min:Math.min(...rows.map((r:any)=>Number(r.refresh_candidates||0))),
      max:Math.max(...rows.map((r:any)=>Number(r.refresh_candidates||0))),
      average:rows.reduce((n:number,r:any)=>n+Number(r.refresh_candidates||0),0)/Math.max(1,rows.length),
      low_count:rows.filter((r:any)=>Number(r.refresh_candidates||0)<Math.max(12,Number(r.generated||0)*1.5)).length
    },
    catalogue_availability:catalogueAvailability,
    catalogue_high_tier_samples:all
      .filter((item:any)=>availabilityInfo(item).rank>=2)
      .map((item:any)=>({
        id:item.id,name:item.name,
        department:department(item,classMap),
        subcategory:classification(item,classMap)?.source_subcategory||null,
        price:basePrice(item),
        price_tier:availabilityInfo(item).tier,
        availability_band:availabilityInfo(item).key
      }))
      .slice(0,120),
    rows
  });
}


function cityRepeatTarget(item:any,eligible:number,classMap:Map<string,any>){
  // Core, support and curated slots are never touched by the citywide balancer,
  // so they already preserve staples and repeat identity stock. A regular or
  // occasional duplicate only needs one surviving copy before its slot becomes
  // available for catalogue coverage.
  return 1;
}

function buildBalancedCityPulse(profiles:any[],all:any[],classMap:Map<string,any>,mfrMap:Map<string,string[]>,generation=0){
  const sellers=profiles.filter((p:any)=>
    isVendrVisibleProfile(p)&&
    ['DIRECT_SELLER','EVENT_MARKET','HYBRID_DIRECT_EVENT'].includes(String(p.stock_mode||''))&&
    !localOnlyProfile(p)&&
    String(stockCuration(p).refresh_mode||'catalog')!=='local'
  );
  const itemById=new Map(all.map((i:any)=>[String(i.id),i]));
  const eligibleCount=new Map<string,number>();
  const scoredByShop=new Map<string,any[]>();

  for(const p of sellers){
    const scored:any[]=[];
    for(const item of all){
      const fit=score(p,item,classMap,mfrMap);
      if(fit===null)continue;
      scored.push({item,fit});
      const id=String(item.id);
      eligibleCount.set(id,(eligibleCount.get(id)||0)+1);
    }
    scoredByShop.set(String(p.entity_id),scored);
  }

  const snapshots=new Map<string,any[]>();
  const coverage=new Map<string,number>();
  for(const p of sellers){
    const rows=stockFor(p,all,classMap,mfrMap,generation).map((r:any)=>({...r}));
    snapshots.set(String(p.entity_id),rows);
    for(const r of rows){
      const id=String(r.item_id);
      coverage.set(id,(coverage.get(id)||0)+1);
    }
  }

  const shopOrder=sellers.slice().sort((a:any,b:any)=>
    stableIndex('city-balance|'+generation+'|'+String(a.entity_id),2147483647)-
    stableIndex('city-balance|'+generation+'|'+String(b.entity_id),2147483647)
  );
  let replacements=0;

  // Keep core/support/curated identity stock intact. Use rotating regular and
  // occasional slots to broaden citywide catalogue exposure.
  for(const role of ['occasional','regular']){
    for(const p of shopOrder){
      const sid=String(p.entity_id);
      const rows=snapshots.get(sid)||[];
      const used=new Set(rows.map((r:any)=>String(r.item_id)));
      const scored=scoredByShop.get(sid)||[];
      const rowIndexes=rows.map((r:any,idx:number)=>({r,idx}))
        .filter((x:any)=>
          String(x.r.assortment_role||'regular')===role&&
          !x.r.support_reason&&!x.r.curation_reason
        )
        .sort((a:any,b:any)=>{
          const ai=String(a.r.item_id),bi=String(b.r.item_id);
          const ac=coverage.get(ai)||0,bc=coverage.get(bi)||0;
          return bc-ac||
            Number(a.r.fit_score||0)-Number(b.r.fit_score||0)||
            stableIndex('city-balance-row|'+sid+'|'+generation+'|'+ai,2147483647)-
            stableIndex('city-balance-row|'+sid+'|'+generation+'|'+bi,2147483647);
        });

      for(const x of rowIndexes){
        const oldId=String(x.r.item_id),oldItem=itemById.get(oldId);
        if(!oldItem)continue;
        const oldCount=coverage.get(oldId)||0;
        const repeatTarget=cityRepeatTarget(oldItem,eligibleCount.get(oldId)||1,classMap);
        if(oldCount<=repeatTarget)continue;

        const oldFit=Number(x.r.fit_score||score(p,oldItem,classMap,mfrMap)||0);
        const fitFloor=oldFit-(role==='occasional'?48:34);
        const oldDep=String(x.r.primary_department||department(oldItem,classMap)||'');

        const candidates=scored
          .filter((c:any)=>{
            const id=String(c.item.id);
            return !used.has(id)&&
              (coverage.get(id)||0)===0&&
              String(department(c.item,classMap)||'')===oldDep&&
              Number(c.fit)>=fitFloor;
          })
          .sort((a:any,b:any)=>
            availabilityInfo(a.item).rank-availabilityInfo(b.item).rank||
            Number(b.fit)-Number(a.fit)||
            stableIndex('city-balance-candidate|'+sid+'|'+generation+'|'+String(a.item.id),2147483647)-
            stableIndex('city-balance-candidate|'+sid+'|'+generation+'|'+String(b.item.id),2147483647)
          );
        const candidate=candidates[0];
        if(!candidate)continue;

        const replacement=stockRowFromChoice(
          p,{item:candidate.item,fit:candidate.fit,role},classMap,generation
        );
        replacement.last_change='citywide assortment balance';
        rows[x.idx]=replacement;
        used.delete(oldId);
        used.add(String(candidate.item.id));
        coverage.set(oldId,oldCount-1);
        coverage.set(String(candidate.item.id),1);
        replacements++;
      }
      snapshots.set(sid,rows);
    }
  }

  const distributed=[...coverage.values()].filter((n:number)=>n>0).length;
  return {
    generation,
    replacements,
    distributed_distinct:distributed,
    distributed_pct:Math.round(distributed/Math.max(1,all.length)*1000)/10,
    shops:sellers.map((p:any)=>({
      entity_id:String(p.entity_id),
      name:String(p.name),
      district:String(p.district||'Night City'),
      snapshot:snapshots.get(String(p.entity_id))||[]
    }))
  };
}

async function pulsePlan(){
  const [all,classMap,mfrMap,profileRows]=await Promise.all([
    catalogue(),classifications(),manufacturers(),
    db('vendr_stock_profiles','select=*&order=name.asc')
  ]);
  const pulse=buildBalancedCityPulse(profileRows,all,classMap,mfrMap,0);
  return out({
    stock_model:LAZY_STOCK_VERSION,
    catalogue_items:all.length,
    generation:pulse.generation,
    replacements:pulse.replacements,
    distributed_distinct:pulse.distributed_distinct,
    distributed_pct:pulse.distributed_pct,
    shops:pulse.shops
  });
}

async function distributionAudit(){
  const [all,classMap,mfrMap,profileRows,observationRows]=await Promise.all([
    catalogue(),classifications(),manufacturers(),
    db('vendr_stock_profiles','select=*&order=name.asc'),
    db('vendr_stock_observations','select=entity_id,generation,state_at,snapshot,model_version&world_key=eq.public-2045')
  ]);
  const profiles=profileRows.filter((p:any)=>
    isVendrVisibleProfile(p)&&
    ['DIRECT_SELLER','EVENT_MARKET','HYBRID_DIRECT_EVENT'].includes(String(p.stock_mode||''))
  );
  const observationMap=new Map(observationRows.map((r:any)=>[String(r.entity_id),r]));
  const byId=new Map<string,any>();
  for(const item of all){
    byId.set(String(item.id),{
      item_id:String(item.id),
      name:displayName(item),
      department:department(item,classMap)||'other',
      subcategory:sourceSubcategory(item,classMap)||null,
      price_tier:availabilityInfo(item).tier,
      seller_count:0,
      tracked_units:0,
      untracked_seller_count:0,
      placements:0,
      sellers:[]
    });
  }

  let observedProfiles=0, initialProfiles=0, totalPlacements=0, trackedUnits=0, untrackedPlacements=0;
  for(const p of profiles){
    if(localOnlyProfile(p)||String(stockCuration(p).refresh_mode||'catalog')==='local') continue;
    const obs:any=observationMap.get(String(p.entity_id));
    const useObserved=Boolean(obs&&String(obs.model_version||'')===LAZY_STOCK_VERSION&&Array.isArray(obs.snapshot));
    if(useObserved) observedProfiles++; else initialProfiles++;
    const raw=useObserved?obs.snapshot:initialSnapshot(p,all,classMap,mfrMap);
    const stock=visibleStock(raw);
    for(const row of stock){
      const id=String(row.item_id||'');
      const a=byId.get(id); if(!a)continue;
      const qty=row.quantity;
      a.seller_count++;
      a.placements++;
      totalPlacements++;
      if(qty==null){
        a.untracked_seller_count++;
        untrackedPlacements++;
      }else{
        const n=Math.max(0,Number(qty)||0);
        a.tracked_units+=n;
        trackedUnits+=n;
      }
      a.sellers.push({
        entity_id:String(p.entity_id),
        shop_name:String(p.name),
        district:String(p.district||'Night City'),
        quantity:qty==null?null:Number(qty),
        condition:row.condition??null,
        assortment_role:row.assortment_role??null
      });
    }
  }

  // Count semantically legitimate seller channels independently of whether
  // an item happened to win a shelf slot in this pulse.
  for(const r of byId.values()){
    const item=all.find((x:any)=>String(x.id)===String(r.item_id));
    if(!item){r.eligible_seller_count=0;continue}
    let eligible=0;
    for(const p of profiles){
      if(localOnlyProfile(p)||String(stockCuration(p).refresh_mode||'catalog')==='local')continue;
      if(score(p,item,classMap,mfrMap)!==null||curationFit(p,item,classMap,mfrMap,'refresh')!==null)eligible++;
    }
    r.eligible_seller_count=eligible;
  }

  const rows=[...byId.values()];
  const distributed=rows.filter((r:any)=>r.seller_count>0);
  const undistributed=rows.filter((r:any)=>r.seller_count===0);
  function median(nums:number[]){
    if(!nums.length)return 0;
    const a=nums.slice().sort((x,y)=>x-y),m=Math.floor(a.length/2);
    return a.length%2?a[m]:(a[m-1]+a[m])/2;
  }
  const bins:any={'1':0,'2':0,'3-5':0,'6-10':0,'11+':0};
  for(const r of distributed){
    const n=Number(r.seller_count||0);
    if(n===1)bins['1']++;
    else if(n===2)bins['2']++;
    else if(n<=5)bins['3-5']++;
    else if(n<=10)bins['6-10']++;
    else bins['11+']++;
  }
  const depMap=new Map<string,any>();
  for(const r of rows){
    const d=String(r.department||'other');
    const x=depMap.get(d)||{department:d,catalogue_items:0,distributed_items:0,placements:0,tracked_units:0,untracked_placements:0};
    x.catalogue_items++;
    if(r.seller_count>0)x.distributed_items++;
    x.placements+=Number(r.placements||0);
    x.tracked_units+=Number(r.tracked_units||0);
    x.untracked_placements+=Number(r.untracked_seller_count||0);
    depMap.set(d,x);
  }
  const departments=[...depMap.values()].map((x:any)=>({
    ...x,coverage_pct:x.catalogue_items?Math.round(x.distributed_items/x.catalogue_items*1000)/10:0
  })).sort((a:any,b:any)=>b.catalogue_items-a.catalogue_items||a.department.localeCompare(b.department));

  const topBySellers=distributed.slice().sort((a:any,b:any)=>
    b.seller_count-a.seller_count||b.tracked_units-a.tracked_units||a.name.localeCompare(b.name)
  ).slice(0,40);
  const topByUnits=distributed.filter((r:any)=>r.tracked_units>0).slice().sort((a:any,b:any)=>
    b.tracked_units-a.tracked_units||b.seller_count-a.seller_count||a.name.localeCompare(b.name)
  ).slice(0,40);

  return out({
    stock_model:LAZY_STOCK_VERSION,
    catalogue_items:all.length,
    seller_profiles:profiles.length,
    state_basis:{
      observed_profiles:observedProfiles,
      deterministic_initial_profiles:initialProfiles,
      local_only_or_local_refresh_profiles:profiles.length-observedProfiles-initialProfiles
    },
    coverage:{
      distributed_distinct:distributed.length,
      undistributed_distinct:undistributed.length,
      distributed_pct:Math.round(distributed.length/Math.max(1,all.length)*1000)/10,
      total_catalogue_placements:totalPlacements,
      tracked_units:trackedUnits,
      untracked_placements:untrackedPlacements,
      median_sellers_per_distributed_item:median(distributed.map((r:any)=>Number(r.seller_count||0))),
      mean_sellers_per_distributed_item:distributed.length?Math.round(totalPlacements/distributed.length*100)/100:0,
      undistributed_but_eligible:undistributed.filter((r:any)=>Number(r.eligible_seller_count||0)>0).length,
      undistributed_without_channel:undistributed.filter((r:any)=>Number(r.eligible_seller_count||0)===0).length,
      seller_count_bins:bins
    },
    departments,
    top_by_sellers:topBySellers,
    top_by_tracked_units:topByUnits,
    items:rows
  });
}

function planFor(p:any){
  const mode=String(p.stock_mode||'');
  const owns=['DIRECT_SELLER','EVENT_MARKET','HYBRID_DIRECT_EVENT'].includes(mode);
  return {stock_mode:mode,owns_stock:owns,action:owns?'read_profile':mode==='AGGREGATE_CONTAINER'?'delegate_to_children':'no_static_inventory'};
}
function profileTypeText(p:any){
  return String((p?.data?.display_tags?.type||[])[0]||p?.primary_archetype||'').trim().toLowerCase();
}
function hasExplicitRetailIdentity(p:any){
  const type=profileTypeText(p);
  const departments=String(p?.primary_departments||'').split('|').map((x:string)=>x.trim()).filter(Boolean);
  const hasNonServiceGoods=departments.some((d:string)=>!['services-entertainment','housing-property','food-consumables'].includes(d));
  return hasNonServiceGoods&&/\b(shop|store|market|boutique|retailer|dealer|stall|pharmacy|outfitter|bookshop|book store)\b/.test(type);
}
function isHospitalityProfile(p:any){
  const type=profileTypeText(p);
  if(!type)return false;
  const hospitality=/\b(restaurant|bar|cafe|café|pub|tavern|nightclub|night club|karaoke|private club|hotel|motel|diner|eatery|food venue|drinking establishment)\b/.test(type);
  return hospitality&&!hasExplicitRetailIdentity(p);
}
function isVendrVisibleProfile(p:any){
  if(!p)return false;
  const visibility=String(p?.data?.vendr_visibility||'').toLowerCase();
  if(visibility==='hidden'||visibility==='exclude')return false;
  const mode=String(p.stock_mode||'');
  if(mode==='SERVICE_ONLY'||mode==='REFERENCE_ONLY'||mode==='CHANNEL_TEMPLATE'||mode==='CHAIN_TEMPLATE')return false;
  if(isHospitalityProfile(p))return false;
  return true;
}
function listingFromProfile(p:any,place:any=null){
  return {
    entity_id:p.entity_id,name:p.name,district:p.district||place?.district||'Night City',
    parent_id:place?.parent_id||p.data?.parent_id||null,
    parent_name:place?.parent_name||p.data?.parent_name||null,
    book_page:p.book_page??place?.book_page??null,source_ref:p.source_ref||place?.source_ref||null,
    entity_level:place?.entity_level||p.entity_level||null,
    commercial_role:place?.commercial_role||null,
    stock_profile_present:true,
    stock_mode:p.stock_mode,action:planFor(p).action,owns_stock:planFor(p).owns_stock,
    type:(p.data?.display_tags?.type||[])[0]||p.primary_archetype||place?.commercial_role||p.stock_mode,
    tags:[...(p.data?.display_tags?.known_for||[]),...(p.data?.display_tags?.trade||[])].join('|'),
    copy:p.data?.short_description||p.modelling_note||'',
    blurb:p.data?.blurb||p.data?.short_description||p.modelling_note||'',
    shop_scale:p.data?.shop_scale||null,
    assortment:p.data?.assortment||null,
    stock_lifecycle:p.data?.stock_lifecycle||null,
    other:p.data?.other||null,
    owner:p.data?.owner||null,
    display_tags:p.data?.display_tags||null,
    local_offering_count:localOfferings(p).length,
    materialized:false,event_id:null
  };
}
function listingFromPlace(p:any){
  const role=p.commercial_role||p.data?.commercial_role||p.entity_level||'Night City place';
  const copy=[role,p.parent_name?('Inside '+p.parent_name):null].filter(Boolean).join(' · ');
  return {
    entity_id:p.entity_id,name:p.display_name,district:p.district||'Night City',
    parent_id:p.parent_id||null,parent_name:p.parent_name||null,book_page:p.book_page,source_ref:p.source_ref,
    entity_level:p.entity_level||null,commercial_role:p.commercial_role||null,
    stock_profile_present:false,stock_mode:'PLACE_ONLY',action:'no_static_inventory',owns_stock:false,
    type:role,tags:p.commercial_role||'',copy,blurb:copy,shop_scale:null,assortment:null,stock_lifecycle:null,
    other:null,owner:null,display_tags:{type:[role],known_for:[],trade:[]},
    materialized:false,event_id:null
  };
}
async function shops(u:URL){
  const activeSources=requestedSourceCodes(u);
  const [placeRows,profileRows,books]=await Promise.all([
    db('vendr_places','select=*&order=district.asc,display_name.asc'),
    db('vendr_stock_profiles','select=*&order=district.asc,name.asc'),
    sourceBooks()
  ]);
  const placeById=new Map(placeRows.map((p:any)=>[String(p.entity_id),p]));
  const rows=profileRows
    .filter((p:any)=>isVendrVisibleProfile(p)&&profileAllowed(p,activeSources,books))
    .map((profile:any)=>{
      const row=listingFromProfile(profile,placeById.get(String(profile.entity_id))||null);
      return {...row,source_code:sourceCodeFromRef(row.source_ref,books)};
    });
  rows.sort((a:any,b:any)=>String(a.district||'').localeCompare(String(b.district||''))||String(a.name||'').localeCompare(String(b.name||'')));
  return out({shops:rows});
}
function stableIndex(value:string,count:number){
  if(count<=0)return 0;
  let h=2166136261;
  for(let i=0;i<value.length;i++){h^=value.charCodeAt(i);h=Math.imul(h,16777619)}
  return (h>>>0)%count;
}
async function shop(u:URL){
  const requestedId=u.searchParams.get('id'); if(!requestedId) return out({error:'missing id'},400);
  const id=canonicalEntityId(requestedId);
  const activeSources=requestedSourceCodes(u);
  const [profileRows,placeRows,edges,visualRows,books,sourceMap]=await Promise.all([
    db('vendr_stock_profiles','select=*&entity_id=eq.'+encodeURIComponent(id)),
    db('vendr_places','select=*&entity_id=eq.'+encodeURIComponent(id)),
    db('vendr_parent_child_edges','select=child_entity_id,child_name,relation_type&parent_entity_id=eq.'+encodeURIComponent(id)),
    db('vendr_visual_profiles','select=*&entity_id=eq.'+encodeURIComponent(id)),
    sourceBooks(),itemSourceMap()
  ]);
  const profile=profileRows[0]||null;
  const place=placeRows[0]||null;
  if(!profile||!isVendrVisibleProfile(profile)||!profileAllowed(profile,activeSources,books)) return out({error:'not listed in active Vend-R sources'},404);

  // Vend-R is retail-only: container pages expose only child profiles that
  // themselves qualify for Vend-R. Service/hospitality/place-only children
  // stay in the place graph for Spaciel but do not leak back into the shop UI.
  const childProfileRows=edges.length
    ?await db('vendr_stock_profiles',
      'select=*&entity_id=in.('+edges.map((e:any)=>String(e.child_entity_id)).join(',')+')')
    :[];
  const visibleChildIds=new Set(
    childProfileRows
      .filter((p:any)=>isVendrVisibleProfile(p)&&profileAllowed(p,activeSources,books))
      .map((p:any)=>String(p.entity_id))
  );
  const vendrEdges=edges.filter((edge:any)=>visibleChildIds.has(String(edge.child_entity_id)));

  const visual=visualRows[0]||null;
  let image=null;
  if(visual?.image_policy==='pool'&&visual.visual_family){
    const poolKey=visual.image_pool_key||visual.visual_family;
    const pool=await db('vendr_image_pool','select=*&enabled=eq.true&visual_family=eq.'+encodeURIComponent(poolKey)+'&order=sort_order.asc');
    if(pool.length){
      const chosen=(visual.image_override&&pool.find((row:any)=>String(row.unsplash_id)===String(visual.image_override)))||pool[stableIndex(id+'|'+poolKey,pool.length)];
      image={
        unsplash_id:chosen.unsplash_id,photographer:chosen.photographer,source_url:chosen.source_url,
        image_url:chosen.image_url,attribution_url:chosen.attribution_url,
        focal_x:Number(chosen.focal_x??0.5),focal_y:Number(chosen.focal_y??0.5),
        visual_family:visual.visual_family,image_pool_key:poolKey,
        visual_condition:visual.visual_condition,visual_setting:visual.visual_setting
      };
    }
  }

  let resolved:any=null;
  let stock:any[]=[];
  let eventRows:any[]=[];
  if(profile){
    const [all,classMap,mfrMap,events]=await Promise.all([
      catalogue(),classifications(),manufacturers(),
      db('vendr_stock_events',
        'select=event_uuid,event_type,item_id,quantity_delta,unit_price,actor_key,occurred_at'+
        '&world_key=eq.public-2045&entity_id=eq.'+encodeURIComponent(id)+
        '&order=occurred_at.desc&limit=8')
    ]);
    eventRows=events;
    resolved=await resolveObservedStock(profile,all,classMap,mfrMap,'public-2045');
    stock=resolved.visible.filter((row:any)=>itemAllowed(row.item_id,sourceMap,activeSources));
  }

  const base=profile||{stock_mode:'PLACE_ONLY'};
  const role=place?.commercial_role||place?.data?.commercial_role||place?.entity_level||'Night City place';
  const placeCopy=place?[role,place.parent_name?('Inside '+place.parent_name):null].filter(Boolean).join(' · '):'';
  const display=profile?.data?.display_tags||{type:[role],known_for:[],trade:[]};
  const type=(display?.type||[])[0]||profile?.primary_archetype||role;
  const tags=profile
    ?[...(display?.known_for||[]),...(display?.trade||[])].join('|')
    :(place?.commercial_role||'');

  return out({
    entity_id:id,name:profile?.name||place?.display_name||'Place',district:profile?.district||place?.district||'Night City',
    parent_id:place?.parent_id||profile?.data?.parent_id||null,
    parent_name:place?.parent_name||profile?.data?.parent_name||null,
    book_page:profile?.book_page??place?.book_page??null,source_ref:profile?.source_ref||place?.source_ref||null,
    source_code:sourceCodeFromRef(profile?.source_ref||place?.source_ref,books),
    entity_level:place?.entity_level||profile?.entity_level||null,commercial_role:place?.commercial_role||null,
    stock_profile_present:Boolean(profile),stock_mode:profile?.stock_mode||'PLACE_ONLY',plan:planFor(base),
    type,tags,
    copy:profile?.data?.blurb||profile?.data?.short_description||profile?.modelling_note||placeCopy,
    short_description:profile?.data?.short_description||profile?.modelling_note||placeCopy,
    blurb:profile?.data?.blurb||profile?.data?.short_description||profile?.modelling_note||placeCopy,
    shop_scale:profile?.data?.shop_scale||null,scale_basis:profile?.data?.scale_basis||null,
    assortment:profile?.data?.assortment||null,stock_lifecycle:profile?.data?.stock_lifecycle||null,
    other:profile?.data?.other||null,owner:profile?.data?.owner||null,display_tags:display,
    modelling_note:profile?.modelling_note||'',children:vendrEdges.map((e:any)=>e.child_entity_id),
    child_places:vendrEdges,
    source_child_count:edges.length,vendr_child_count:vendrEdges.length,
    unnamed_retail:profile?.data?.unnamed_retail||null,
    event_id:null,materialized:false,stock,
    local_offerings:profile?localOfferings(profile).filter((x:any)=>offeringAllowed(x,activeSources,books)):[],
    state:resolved?.snapshot?.length?{
      stock_cycle:resolved.generation,generation:resolved.generation,state_at:resolved.state_at,
      first_observation:resolved.first_observation,catchup_mutations:resolved.mutations,
      elapsed_days:resolved.elapsed_days,cadence_label:'Updates when checked',
      turnover:lifecycle(profile)?.turnover||null,lazy_model_version:LAZY_STOCK_VERSION,
      assortment_count:stock.length,incoming_count:0,history_count:eventRows.length
    }:null,
    source_contract:null,events:eventRows,visual_profile:visual,image,
    stock_snapshot:resolved?.snapshot?.length?('observed_'+resolved.generation):null,
    catalog_match:profile?.data?.catalog_match||null,
    service_note:profile?.data?.service_note||null,
    source_note:profile?.data?.source_note||null,
    access_note:profile?.data?.access_note||null,
    trusted_stock_note:profile?.data?.trusted_stock_note||
      (profile?.data?.catalog_match?.strategy==='tiered'?'Additional stock may be available to trusted customers.':null)
  });
}


// Browser UI lives at https://bardofcarnac.github.io/Catalogger/.
// Keep this function focused on API/backend behavior.

Deno.serve(async(req:Request)=>{
  if(req.method==='OPTIONS') return new Response('ok',{headers:JH});
  try{
    const u=new URL(req.url), a=u.searchParams.get('api');
    if(a==='health') return await health();
    if(a==='stock_audit') return await stockAudit();
    if(a==='distribution_audit') return await distributionAudit();
    if(a==='pulse_plan') return await pulsePlan();
    if(a==='sources') return await sourcesApi(u);
    if(a==='shops') return await shops(u);
    if(a==='search') return await search(u);
    if(a==='item') return await itemDetail(u);
    if(a==='shop') return await shop(u);
    if(a==='purchase') return await purchase(req);
    if(a==='debug-item'){
      const id=u.searchParams.get('id');
      const [all,classMap,mfrMap]=await Promise.all([catalogue(),classifications(),manufacturers()]);
      const item=id?all.find((x:any)=>String(x.id)===String(id)):all[0];
      return out(item?{
        item,
        classification:classification(item,classMap),
        department:department(item,classMap),
        relation_key:relationKey(item,classMap),
        manufacturers:mfrMap.get(String(item.id))||[],
        quantity_class:quantityClass(item,classMap),
        base_price:basePrice(item)
      }:null)
    }
    return Response.redirect('https://bardofcarnac.github.io/Catalogger/',302);
  }catch(e){return out({error:e instanceof Error?e.message:String(e)},500)}
});