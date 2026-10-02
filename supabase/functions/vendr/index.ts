const ROOT = 'https://raw.githubusercontent.com/BardOfCarnac/Catalogger/vendr-live-catalogger-demo/';
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
let cache: Promise<any[]> | null = null;
let classCache: Promise<Map<string,any>> | null = null;
let mfrCache: Promise<Map<string,string[]>> | null = null;

async function gunzipJson(url:string){
  const r=await fetch(url,{headers:{'user-agent':'Vend-R/0.1'}});
  if(!r.ok) throw new Error('catalogue fetch failed: '+r.status);
  const ds=new DecompressionStream('gzip');
  return JSON.parse(await new Response(r.body!.pipeThrough(ds)).text());
}
function catalogue(){
  if(!cache) cache=Promise.all(PARTS.map(p=>gunzipJson(ROOT+p))).then(x=>x.flat());
  return cache;
}
function classifications(){
  if(!classCache) classCache=Promise.all(CLASS_PARTS.map(p=>gunzipJson(ROOT+p))).then(parts=>{
    const map=new Map<string,any>();
    for(const row of parts.flat()){
      const id=String(row.item_id);
      const current=map.get(id);
      if(!current||row.is_primary) map.set(id,row);
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
function textHit(i:any,terms:any[]){const n=String(i?.name||'').toLowerCase();return (terms||[]).some(t=>n.includes(String(t).toLowerCase()))}
function ruleAllows(p:any,i:any,classMap:Map<string,any>,mfrMap:Map<string,string[]>){
  const rule=matchRule(p);
  if(!rule) return {allow:true,boost:0};
  if(rule.strategy==='no_catalog_stock') return {allow:false,boost:0};
  const d=department(i,classMap), sub=String(classification(i,classMap)?.source_subcategory||'');
  const allowedDeps=rule.allowed_departments||[];
  if(allowedDeps.length&&(!d||!allowedDeps.includes(d))) return {allow:false,boost:0};
  if((rule.exclude_departments||[]).includes(d)) return {allow:false,boost:0};
  const hardSubs=rule.allowed_subcategories||[];
  if(hardSubs.length&&(!sub||!hardSubs.includes(sub))) return {allow:false,boost:0};
  const itemMfrs=mfrMap.get(String(i.id))||[];
  const required=rule.required_manufacturers||[];
  if(required.length&&!itemMfrs.some(x=>required.includes(x))&&!rule.allow_unbranded) return {allow:false,boost:0};
  let boost=0;
  if((rule.preferred_subcategories||[]).includes(sub)) boost+=35;
  if((rule.preferred_manufacturers||[]).some((x:string)=>itemMfrs.includes(x))) boost+=28;
  if(textHit(i,rule.preferred_name_terms||rule.name_boost_terms||[])) boost+=24;
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
  if(d&&pri.includes(d)) s=100; else if(d&&sec.includes(d)) s=55; else if(d) return null; else s=15;
  const max=Number(matchRule(p)?.max_base_price_eb??p.max_base_price_eb), price=basePrice(i);
  if(Number.isFinite(max)&&max>0&&price!==null&&price>max) return null;
  if(p.breadth_profile==='broad') s+=10;
  if(p.assignment_confidence==='HIGH') s+=5;
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
  const fallback:any={
    compact:[6,10],small:[8,14],medium:[12,22],broad:[18,32],extensive:[28,48]
  };
  const fb=fallback[String(p.breadth_profile||'medium').toLowerCase()]||fallback.medium;
  const lo=Math.max(0,Number.isFinite(Number(a.capacity_min))?Number(a.capacity_min):fb[0]);
  const hi=Math.max(lo,Number.isFinite(Number(a.capacity_max))?Number(a.capacity_max):fb[1]);
  const total=lo+(hi>lo?stableIndex('cycle1|'+p.entity_id+'|capacity',hi-lo+1):0);
  if(total<=0)return {core:0,regular:0,occasional:0,total:0};
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
  if(subs.length&&subs.includes(sub))return true;
  if(deps.length&&dep&&deps.includes(dep))return true;
  return !subs.length&&!deps.length;
}

function lifecycle(p:any){return p?.data?.stock_lifecycle||{mode:'scheduled',cadence_hours:168,cadence_label:'Weekly',turnover:'steady',rotation:{core_cycles:null,regular_cycles:3,occasional_cycles:1}}}
function cycleInfo(p:any,nowMs=Date.now()){
  const l=lifecycle(p), hours=Number(l.cadence_hours);
  if(!Number.isFinite(hours)||hours<=0)return {cycle:1,next_restock_at:null,cadence_label:l.cadence_label||'No shelf stock',turnover:l.turnover||null};
  const ms=hours*3600000;
  const cycle=Math.floor(nowMs/ms);
  const next=(cycle+1)*ms;
  return {cycle,next_restock_at:new Date(next).toISOString(),cadence_label:l.cadence_label||null,turnover:l.turnover||null};
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
function selectRole(p:any,ranked:any[],count:number,classMap:Map<string,any>,used:Set<string>,role:string,cycle:number){
  if(count<=0)return [];
  const explicit=Array.isArray(p?.data?.assortment?.shape)?p.data.assortment.shape:[];
  const shape=explicit.length?explicit:defaultShape(p);
  const ordered=roleOrder(p,ranked,role,cycle);
  const selected:any[]=[];
  if(shape.length){
    for(const bucket of shape){
      if(selected.length>=count)break;
      const target=Math.max(1,Math.round(count*Number(bucket.weight||0)));
      let got=0;
      for(const row of ordered){
        if(selected.length>=count||got>=target)break;
        const id=String(row.item.id);
        if(used.has(id)||!itemMatchesBucket(row.item,bucket,classMap))continue;
        selected.push({...row,role});used.add(id);got++;
      }
    }
  }
  for(const row of ordered){
    if(selected.length>=count)break;
    const id=String(row.item.id);
    if(used.has(id))continue;
    selected.push({...row,role});used.add(id);
  }
  return selected;
}
function selectAssortment(p:any,ranked:any[],plan:any,classMap:Map<string,any>,cycle:number){
  const used=new Set<string>();const selected:any[]=[];
  for(const role of ['core','regular','occasional']){
    selected.push(...selectRole(p,ranked,Number(plan[role]||0),classMap,used,role,cycle));
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
  const m:any={bargain:.90,fair:1,premium:1.12,gouging:1.28};
  return m[String(p?.pricing_style||'fair').toLowerCase()]||1;
}
function cyclePrice(p:any,i:any,cycle:number){
  const base=basePrice(i); if(base===null) return null;
  const jitter=(stableIndex('price|'+cycle+'|'+p.entity_id+'|'+i.id,1201)-600)/10000;
  const value=Math.max(.01,base*pricingMultiplier(p)*(1+jitter));
  return value<10?Math.round(value*100)/100:Math.round(value);
}
function stockCondition(p:any,i:any,cycle:number){
  const options=matchRule(p)?.allowed_conditions;
  if(!Array.isArray(options)||!options.length)return 'new';
  return options[stableIndex('condition|'+cycle+'|'+p.entity_id+'|'+i.id,options.length)];
}
function stockFor(p:any,all:any[],classMap:Map<string,any>,mfrMap:Map<string,string[]>){
  if(!['DIRECT_SELLER','EVENT_MARKET','HYBRID_DIRECT_EVENT'].includes(String(p.stock_mode||''))) return [];
  const ci=cycleInfo(p),plan=assortmentPlan(p);
  const ranked=all.map((item:any)=>({item,fit:score(p,item,classMap,mfrMap)}))
    .filter((x:any)=>x.fit!==null);
  const chosen=selectAssortment(p,ranked,plan,classMap,ci.cycle);
  return chosen.map((x:any)=>({
    item_id:String(x.item.id),
    name:x.item.name,
    quantity:cycleQuantity(p,x.item,classMap,x.role,ci.cycle),
    quantity_profile:quantityClass(x.item,classMap),
    condition:stockCondition(p,x.item,ci.cycle),
    asking_price:cyclePrice(p,x.item,ci.cycle),
    visibility:'public',
    status:'in_stock',
    assortment_role:x.role,
    primary_department:department(x.item,classMap),
    relation_key:relationKey(x.item,classMap),
    fit_score:x.fit,
    stock_cycle:ci.cycle
  }));
}
function depletionKey(entityId:string,cycle:number,itemId:string){return entityId+'|'+cycle+'|'+itemId}
function applyDepletionRows(p:any,stock:any[],rows:any[]){
  const cycle=cycleInfo(p).cycle;
  const map=new Map(rows
    .filter((r:any)=>String(r.entity_id)===String(p.entity_id)&&Number(r.stock_cycle)===Number(cycle))
    .map((r:any)=>[String(r.item_id),{
      baseline_quantity:r.baseline_quantity==null?null:Number(r.baseline_quantity),
      quantity_depleted:Number(r.quantity_depleted||0)
    }]));
  return stock.map((row:any)=>{
    if(row.quantity==null)return {...row,baseline_quantity:null,quantity_depleted:0};
    const persisted:any=map.get(String(row.item_id))||null;
    const baseline=persisted?.baseline_quantity??Number(row.quantity);
    const depleted=Number(persisted?.quantity_depleted||0);
    const remaining=Math.max(0,baseline-depleted);
    return {...row,baseline_quantity:baseline,quantity_depleted:depleted,quantity:remaining,status:remaining>0?'in_stock':'sold'};
  }).filter((row:any)=>row.quantity==null||row.quantity>0);
}
async function depletionForShop(p:any,worldKey='public-2045'){
  const cycle=cycleInfo(p).cycle;
  return await db('vendr_stock_depletion',
    'select=entity_id,item_id,stock_cycle,baseline_quantity,quantity_depleted,updated_at'+
    '&world_key=eq.'+encodeURIComponent(worldKey)+
    '&entity_id=eq.'+encodeURIComponent(String(p.entity_id))+
    '&stock_cycle=eq.'+encodeURIComponent(String(cycle))
  );
}

async function search(u:URL){
  const q=(u.searchParams.get('q')||'').trim();
  const activeId=u.searchParams.get('item_id');
  const suggestOnly=u.searchParams.get('suggest')==='1';
  if(!q) return out({query:q,active_item_id:null,items:[],offers:[],total_matches:0});

  const [all,classMap]=await Promise.all([catalogue(),classifications()]);
  const f=q.toLowerCase();

  // Start with literal catalogue-name matches, then expand through their
  // Catalogger classification so a broad term like "pistol" also finds
  // named pistol models which do not contain the word "pistol".
  const direct=all.filter((i:any)=>String(i.name||'').toLowerCase().includes(f));
  const relatedKeys=new Set(direct.map((i:any)=>relationKey(i,classMap)).filter(Boolean));

  const matches=all.filter((i:any)=>{
    const name=String(i.name||'').toLowerCase();
    return name.includes(f) || relatedKeys.has(relationKey(i,classMap));
  }).sort((a:any,b:any)=>{
    const an=String(a.name||''),bn=String(b.name||''),af=an.toLowerCase(),bf=bn.toLowerCase();
    const ad=af.includes(f),bd=bf.includes(f);
    const ar=af===f?0:af.startsWith(f)?1:ad?2:3;
    const br=bf===f?0:bf.startsWith(f)?1:bd?2:3;
    return ar-br||an.length-bn.length||an.localeCompare(bn);
  });

  const itemRows=matches.map((i:any)=>({
    item_id:i.id,
    name:i.name,
    primary_department:department(i,classMap),
    relation_key:relationKey(i,classMap)
  }));

  if(suggestOnly){
    return out({
      query:q,
      active_item_id:null,
      items:itemRows.slice(0,10),
      total_matches:itemRows.length,
      offers:[]
    });
  }

  const active=activeId?matches.find((i:any)=>String(i.id)===activeId):null;
  const mfrMap=await manufacturers();
  const [profiles,placeRows,depletionRows]=await Promise.all([
    db('vendr_stock_profiles','select=*&order=name.asc'),
    db('vendr_places','select=entity_id,parent_name,district,spatial_mode'),
    db('vendr_stock_depletion','select=entity_id,item_id,stock_cycle,baseline_quantity,quantity_depleted&world_key=eq.public-2045')
  ]);
  const placeMap=new Map(placeRows.map((r:any)=>[String(r.entity_id),r]));
  const offerItems=active?[active]:matches.slice(0,12);
  const stockCache=new Map<string,any[]>();
  const offers:any[]=[];

  for(const item of offerItems){
    const itemId=String(item.id);
    for(const p of profiles){
      const fit=score(p,item,classMap,mfrMap); if(fit===null) continue;
      let stock=stockCache.get(String(p.entity_id));
      if(!stock){
        stock=applyDepletionRows(p,stockFor(p,all,classMap,mfrMap),depletionRows);
        stockCache.set(String(p.entity_id),stock)
      }
      const row=stock.find((r:any)=>String(r.item_id)===itemId);
      const place=placeMap.get(String(p.entity_id))||{};
      offers.push({
        kind:row?'available':'plausible',
        item_id:itemId,item_name:item.name,
        primary_department:department(item,classMap),relation_key:relationKey(item,classMap),
        shop_entity_id:p.entity_id,shop_name:p.name,
        district:place.district||p.district,
        parent_name:place.parent_name||null,
        spatial_mode:place.spatial_mode||null,
        distance:null,
        score:fit,stock_mode:p.stock_mode,
        quantity:row?.quantity??null,asking_price:row?.asking_price??null,
        condition:row?.condition??null,stock_cycle:row?.stock_cycle??null
      });
    }
  }

  offers.sort((a,b)=>(a.kind!=='available')-(b.kind!=='available')||Number(b.score)-Number(a.score)||String(a.shop_name).localeCompare(String(b.shop_name)));
  return out({
    query:q,
    active_item_id:active?String(active.id):null,
    items:itemRows,
    offers:offers.slice(0,60),
    total_matches:itemRows.length,
    catalogue_count:all.length,
    seller_profile_count:profiles.length,
    stock_cycle:null
  });
}

async function purchase(req:Request){
  if(req.method!=='POST')return out({error:'POST required'},405);
  const user=await authenticatedUser(req);
  if(!user)return out({error:'Authentication required for stock mutation'},401);

  const body=await req.json().catch(()=>null);
  const entityId=String(body?.entity_id||'');
  const itemId=String(body?.item_id||'');
  const quantity=Math.max(1,Math.floor(Number(body?.quantity||1)));
  const worldKey=String(body?.world_key||'public-2045');
  if(!entityId||!itemId||!Number.isFinite(quantity))return out({error:'entity_id, item_id and a positive quantity are required'},400);

  const profiles=await db('vendr_stock_profiles','select=*&entity_id=eq.'+encodeURIComponent(entityId));
  const p=profiles[0];
  if(!p)return out({error:'shop not found'},404);
  if(!['DIRECT_SELLER','EVENT_MARKET','HYBRID_DIRECT_EVENT'].includes(String(p.stock_mode||'')))return out({error:'place does not own shelf stock'},409);

  const [all,classMap,mfrMap,depletionRows]=await Promise.all([
    catalogue(),classifications(),manufacturers(),depletionForShop(p,worldKey)
  ]);
  const baseline=stockFor(p,all,classMap,mfrMap);
  const current=applyDepletionRows(p,baseline,depletionRows);
  const currentRow=current.find((r:any)=>String(r.item_id)===itemId);
  const baselineRow=baseline.find((r:any)=>String(r.item_id)===itemId);
  if(!baselineRow)return out({error:'item is not in this shop cycle'},409);

  if(baselineRow.quantity==null){
    await dbInsert('vendr_stock_events',{
      world_key:worldKey,entity_id:entityId,item_id:itemId,stock_cycle:cycleInfo(p).cycle,
      event_type:'purchase',quantity_delta:-quantity,unit_price:baselineRow.asking_price,
      actor_key:String(user.id),metadata:{quantity_mode:'continuous',non_depleting:true}
    });
    return out({ok:true,depletes:false,entity_id:entityId,item_id:itemId,quantity_purchased:quantity,remaining:null,stock_cycle:cycleInfo(p).cycle});
  }

  const available=Number(currentRow?.quantity||0);
  if(quantity>available)return out({error:'insufficient stock',available},409);

  try{
    const result=await rpc('vendr_apply_purchase',{
      p_world_key:worldKey,
      p_entity_id:entityId,
      p_item_id:itemId,
      p_stock_cycle:cycleInfo(p).cycle,
      p_quantity:quantity,
      p_baseline_quantity:Number(baselineRow.quantity),
      p_unit_price:baselineRow.asking_price,
      p_actor_key:String(user.id),
      p_metadata:{surface:'vendr-live',quantity_mode:baselineRow.quantity_profile||'finite'}
    });
    return out(result);
  }catch(e:any){
    if(String(e?.message||'').toLowerCase().includes('insufficient stock'))return out({error:'insufficient stock'},409);
    throw e;
  }
}
async function health(){
  const all=await catalogue(), profiles=await db('vendr_stock_profiles','select=entity_id'), places=await db('vendr_places','select=entity_id');
  return out({ok:true,service:'vend-r-supabase',catalog_items:all.length,profiles:profiles.length,places:places.length,read_only:true});
}
function planFor(p:any){
  const mode=String(p.stock_mode||'');
  const owns=['DIRECT_SELLER','EVENT_MARKET','HYBRID_DIRECT_EVENT'].includes(mode);
  return {stock_mode:mode,owns_stock:owns,action:owns?'read_profile':mode==='AGGREGATE_CONTAINER'?'delegate_to_children':'no_static_inventory'};
}
async function shops(){
  const rows=await db('vendr_stock_profiles','select=*&order=district.asc,name.asc');
  return out({shops:rows.map((p:any)=>({
    entity_id:p.entity_id,name:p.name,district:p.district,parent_name:null,book_page:p.book_page,source_ref:p.source_ref,
    stock_mode:p.stock_mode,action:planFor(p).action,owns_stock:planFor(p).owns_stock,
    type:(p.data?.display_tags?.type||[])[0]||p.primary_archetype||p.stock_mode,
    tags:[...(p.data?.display_tags?.known_for||[]),...(p.data?.display_tags?.trade||[])].join('|'),
    copy:p.data?.short_description||p.modelling_note||'',
    blurb:p.data?.blurb||p.data?.short_description||p.modelling_note||'',
    shop_scale:p.data?.shop_scale||null,
    assortment:p.data?.assortment||null,
    stock_lifecycle:p.data?.stock_lifecycle||null,
    other:p.data?.other||null,
    owner:p.data?.owner||null,
    display_tags:p.data?.display_tags||null,
    materialized:false,event_id:null
  }))});
}
function stableIndex(value:string,count:number){
  if(count<=0)return 0;
  let h=2166136261;
  for(let i=0;i<value.length;i++){h^=value.charCodeAt(i);h=Math.imul(h,16777619)}
  return (h>>>0)%count;
}
async function shop(u:URL){
  const id=u.searchParams.get('id'); if(!id) return out({error:'missing id'},400);
  const rows=await db('vendr_stock_profiles','select=*&entity_id=eq.'+encodeURIComponent(id));
  if(!rows[0]) return out({error:'not found'},404);
  const p=rows[0];
  const ci=cycleInfo(p);
  const [edges,visualRows,all,classMap,mfrMap,depletionRows,eventRows]=await Promise.all([
    db('vendr_parent_child_edges','select=child_entity_id,child_name,relation_type&parent_entity_id=eq.'+encodeURIComponent(id)),
    db('vendr_visual_profiles','select=*&entity_id=eq.'+encodeURIComponent(id)),
    catalogue(),
    classifications(),
    manufacturers(),
    depletionForShop(p,'public-2045'),
    db('vendr_stock_events',
      'select=event_uuid,event_type,item_id,stock_cycle,quantity_delta,unit_price,actor_key,occurred_at'+
      '&world_key=eq.public-2045&entity_id=eq.'+encodeURIComponent(id)+
      '&stock_cycle=eq.'+encodeURIComponent(String(ci.cycle))+
      '&order=occurred_at.desc&limit=8')
  ]);
  const visual=visualRows[0]||null;
  let image=null;
  if(visual?.image_policy==='pool'&&visual.visual_family){
    const poolKey=visual.image_pool_key||visual.visual_family;
    const pool=await db('vendr_image_pool','select=*&enabled=eq.true&visual_family=eq.'+encodeURIComponent(poolKey)+'&order=sort_order.asc');
    if(pool.length){
      const chosen=pool[stableIndex(id+'|'+poolKey,pool.length)];
      image={
        unsplash_id:chosen.unsplash_id,
        photographer:chosen.photographer,
        source_url:chosen.source_url,
        image_url:chosen.image_url,
        attribution_url:chosen.attribution_url,
        focal_x:Number(chosen.focal_x??0.5),
        focal_y:Number(chosen.focal_y??0.5),
        visual_family:visual.visual_family,
        image_pool_key:poolKey,
        visual_condition:visual.visual_condition,
        visual_setting:visual.visual_setting
      };
    }
  }
  const stock=applyDepletionRows(p,stockFor(p,all,classMap,mfrMap),depletionRows);
  return out({
    entity_id:p.entity_id,name:p.name,district:p.district,
    parent_name:(p.data?.parent_name||null),book_page:p.book_page,source_ref:p.source_ref,
    stock_mode:p.stock_mode,plan:planFor(p),
    type:(p.data?.display_tags?.type||[])[0]||p.primary_archetype||p.stock_mode,
    tags:[...(p.data?.display_tags?.known_for||[]),...(p.data?.display_tags?.trade||[])].join('|'),
    copy:p.data?.blurb||p.data?.short_description||p.modelling_note||'',
    short_description:p.data?.short_description||p.modelling_note||'',
    blurb:p.data?.blurb||p.data?.short_description||p.modelling_note||'',
    shop_scale:p.data?.shop_scale||null,
    scale_basis:p.data?.scale_basis||null,
    assortment:p.data?.assortment||null,
    stock_lifecycle:p.data?.stock_lifecycle||null,
    other:p.data?.other||null,
    owner:p.data?.owner||null,
    display_tags:p.data?.display_tags||null,
    modelling_note:p.modelling_note||'',children:edges.map((e:any)=>e.child_entity_id),
    child_places:edges,event_id:null,materialized:false,stock,
    state:stock.length?{...cycleInfo(p),assortment_count:stock.length,incoming_count:0,history_count:0}:null,
    source_contract:null,events:eventRows,visual_profile:visual,image,
    stock_snapshot:stock.length?('cycle_'+cycleInfo(p).cycle):null,
    catalog_match:p.data?.catalog_match||null,
    trusted_stock_note:p.data?.catalog_match?.strategy==='tiered'?'Additional stock may be available to trusted customers.':null
  });
}

const HTML=`<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vend-R · Night City 2045</title>
<style>
:root{--a:#ef5a2f;--b:#ffc84c;--cream:#f4eddf;--paper:#fbf5e9;--ink:#171713;--muted:#6f685f;--line:#c7baa7;--dark:#252521;--red:#d94a34;--blue:#627d89}
*{box-sizing:border-box}
body{margin:0;font-family:Arial,Helvetica,sans-serif;color:var(--ink);background:linear-gradient(135deg,var(--a) 0 34%,#f47f35 34.5%,var(--b) 72%,#ffe07a)}
.shell{width:min(1180px,calc(100% - 24px));min-height:calc(100vh - 36px);margin:18px auto;background:var(--cream);box-shadow:14px 18px 40px #6c321f44;border:1px solid #6b4b2f33}
header{height:62px;display:flex;align-items:center;padding:0 22px;border-bottom:1px solid var(--line);gap:18px;position:sticky;top:0;background:#f4eddfed;backdrop-filter:blur(8px);z-index:40}
.brand{font-size:19px;font-weight:950;letter-spacing:.05em}.mark{display:inline-grid;place-items:center;width:30px;height:30px;color:#fff;background:linear-gradient(135deg,var(--red),var(--b));clip-path:polygon(50% 0,100% 25%,82% 100%,18% 100%,0 25%);margin-right:8px}
.status{margin-left:auto;font:700 9px monospace;color:#68765d}
main{padding:34px 28px 70px}
.k{font-size:9px;letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:800}
h1{font-size:clamp(56px,9vw,108px);line-height:.79;letter-spacing:-.065em;margin:11px 0 24px}
h2{font-size:28px;margin:6px 0}h3{margin:4px 0;font-size:18px}
.hero{display:grid;grid-template-columns:1.05fr .95fr;gap:36px;align-items:end}.hero p{color:#524b42;line-height:1.45}
.search-wrap{position:relative}
.search{display:flex;border:2px solid var(--dark);background:#fffaf0;padding:6px}
.search input{flex:1;min-width:0;border:0;background:transparent;font-size:19px;padding:12px;outline:none}
.search button{border:0;background:var(--red);color:#fff;font-weight:900;padding:12px 18px;cursor:pointer}
.suggest{position:absolute;left:0;right:0;top:calc(100% + 6px);z-index:60;background:#fffaf0;border:2px solid var(--dark);box-shadow:9px 9px 0 #d9cbb8;max-height:min(62vh,520px);overflow:auto}
.suggest.hidden{display:none}.suggest-head{padding:8px 11px;border-bottom:1px solid var(--line);font:800 9px monospace;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.suggest button{display:block;width:100%;border:0;border-bottom:1px solid var(--line);background:transparent;text-align:left;padding:11px 12px;cursor:pointer;color:var(--ink)}
.suggest button:hover{background:#fff0c6}.suggest button strong{display:block;font-size:14px;text-transform:uppercase}.suggest button span{display:block;margin-top:4px;font:800 8px monospace;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
.suggest .all{background:var(--b);border-top:2px solid var(--dark)}
.view.hidden{display:none}
.search-head{display:flex;justify-content:space-between;gap:16px;align-items:end;border-bottom:4px solid var(--dark);padding-bottom:12px;margin-bottom:18px}
.search-head h1{font-size:clamp(44px,8vw,88px);margin:8px 0 0}.back{border:0;background:none;text-decoration:underline;padding:0;cursor:pointer}
.search-again{margin:0 0 24px}
.block{margin-top:18px}.block-head{display:flex;justify-content:space-between;align-items:end;gap:12px;border-bottom:3px solid var(--dark);padding-bottom:8px}.block-head span{font:800 9px monospace;color:var(--muted);text-transform:uppercase}
.results{display:grid;gap:8px;padding-top:8px}
.row{border:1px solid var(--line);background:var(--paper);padding:13px 13px 13px 18px;display:grid;grid-template-columns:1.2fr .9fr auto;gap:14px;text-align:left;position:relative;cursor:pointer}
.row:before{content:"";position:absolute;left:0;top:0;bottom:0;width:5px;background:var(--blue)}.row:hover{background:#fffaf0}.row b{display:block;font-size:14px}.row span{display:block;font-size:8px;color:var(--muted);text-transform:uppercase;letter-spacing:.07em;margin-top:4px}.row .price{text-align:right;min-width:92px}.row .price b{font-size:17px}.row.exact{grid-template-columns:1fr auto}.row.exact .item{display:none}.row.plausible:before{background:#b4a896}.row.plausible .price b{font-size:10px;color:var(--muted)}
.panel{border:1px solid var(--line);padding:16px;background:#e9dfcf}.empty{margin-top:20px}
.card{background:var(--paper);border:1px solid var(--line);box-shadow:9px 9px 0 #d9cbb8}.sign{background:var(--dark);color:#fff;padding:28px}.sign h1{font-size:clamp(48px,8vw,88px)}.body{display:grid;grid-template-columns:1.6fr .7fr}.main,.aside{padding:24px}.aside{border-left:1px solid var(--line);background:#e9dfcf}
.stock-row{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:12px;align-items:center;padding:10px 0;border-bottom:1px solid var(--line)}.stock-row:last-child{border-bottom:0}.stock-row small{display:block;color:var(--muted);text-transform:uppercase}.stock-row .qty,.stock-row .ask{font:800 11px monospace}.stock-row.focus b{color:#c84d1d}
.children button{display:block;width:100%;text-align:left;padding:10px;border:1px solid var(--line);background:#fffaf0;margin-top:7px}
@media(max-width:800px){.hero,.body{grid-template-columns:1fr}.hero{gap:20px}.row{grid-template-columns:1fr auto}.row .seller{grid-column:1}.row .price{grid-column:2;grid-row:1/3}.aside{border-left:0;border-top:1px solid var(--line)}main{padding:24px 16px}.search-head{align-items:start;flex-direction:column}.search-head h1{font-size:54px}}
</style>
</head>
<body>
<div class="shell">
<header><div class="brand"><span class="mark">V</span>VEND-R</div><div class="k">Night City 2045</div><div id="status" class="status">CONNECTING</div></header>
<main>
<section id="home" class="view">
  <div class="hero">
    <div><div class="k">Night City stock index</div><h1>FIND IT<br>BEFORE YOU<br>INVENT IT.</h1><p>Search the actual Catalogger catalogue against Vend-R's canonical Night City commercial profiles. Choose a catalogue object as you type, or press Enter to search the broader idea.</p></div>
    <div class="search-wrap">
      <form id="homeForm" class="search"><input id="homeQ" placeholder="pistol, Agent, armor…" autocomplete="off"><button>SEARCH</button></form>
      <div id="suggest" class="suggest hidden"></div>
    </div>
  </div>
</section>

<section id="resultsView" class="view hidden">
  <div class="search-head"><div><div id="mode" class="k">Broad search</div><h1 id="title">SEARCH</h1></div><button id="homeBack" class="back">← Market</button></div>
  <form id="resultsForm" class="search search-again"><input id="resultsQ" placeholder="SEARCH AGAIN" autocomplete="off"><button>SEARCH</button></form>
  <div id="searchNote" class="k"></div>
  <section id="availableBlock" class="block"><div class="block-head"><h2 id="availableTitle">AVAILABLE NOW</h2><span id="availableMeta"></span></div><div id="available" class="results"></div></section>
  <section id="likelyBlock" class="block"><div class="block-head"><h2>OTHER LIKELY SELLERS</h2><span>PROFILE FIT · NOT CURRENT STOCK</span></div><div id="likely" class="results"></div></section>
  <div id="empty" class="panel empty hidden">No current Vend-R matches.</div>
</section>

<section id="shopView" class="view hidden">
  <button id="shopBack" class="back">← Back to search</button>
  <article class="card">
    <div class="sign"><div id="smode" class="k"></div><h1 id="sname"></h1><div id="sdistrict"></div></div>
    <div class="body">
      <div class="main"><div class="k">Commercial profile</div><h2 id="stype"></h2><p id="snote"></p><div id="stock"></div><div id="children" class="children"></div></div>
      <aside class="aside"><div class="k">Source</div><p id="ssource"></p><div class="k">Departments</div><p id="sdeps"></p></aside>
    </div>
  </article>
</section>
</main>
</div>
<script>
const $=id=>document.getElementById(id);
const state={q:"",item:null,data:null,focus:null};
async function api(p){const u=new URL(location.href);u.search="";Object.entries(p).forEach(x=>x[1]!=null&&x[1]!==""&&u.searchParams.set(x[0],x[1]));const r=await fetch(u);const j=await r.json();if(!r.ok)throw new Error(j.error||r.statusText);return j}
function esc(s){return String(s==null?"":s).replace(/[&<>'"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]))}
function show(name){["home","resultsView","shopView"].forEach(id=>$(id).classList.toggle("hidden",id!==name));scrollTo(0,0)}
function typeLabel(x){return String(x.primary_department||"item").replaceAll("-"," ")}
function placeLabel(x){return [x.parent_name,x.district,x.distance].filter(Boolean).join(" · ")||"Night City"}
function money(v){return v==null?"—":Number(v).toLocaleString()+"eb"}
async function health(){try{const x=await api({api:"health"});$("status").textContent="CONNECTED · "+x.catalog_items+" ITEMS · "+x.profiles+" SELLER PROFILES"}catch(_){$("status").textContent="OFFLINE"}}

let suggestTimer=null,suggestToken=0;
function hideSuggest(){$("suggest").classList.add("hidden");$("suggest").innerHTML=""}
function renderSuggest(d,q){const items=d.items||[],total=Number(d.total_matches||items.length);$("suggest").innerHTML='<div class="suggest-head">Catalogue suggestions</div>'+items.map(x=>'<button type="button" data-item="'+esc(x.item_id)+'"><strong>'+esc(x.name)+'</strong><span>'+esc(typeLabel(x))+' · exact catalogue item</span></button>').join("")+'<button type="button" class="all" data-all="1"><strong>Search all “'+esc(q)+'”</strong><span>'+esc(total)+' related catalogue item'+(total===1?"":"s")+' →</span></button>';$("suggest").classList.remove("hidden");$("suggest").querySelectorAll("[data-item]").forEach(b=>b.onclick=()=>runSearch(q,b.dataset.item,true));$("suggest").querySelector("[data-all]").onclick=()=>runSearch(q,null,true)}
function queueSuggest(raw){const q=String(raw||"").trim();clearTimeout(suggestTimer);if(q.length<2){hideSuggest();return}const token=++suggestToken;suggestTimer=setTimeout(async()=>{try{const d=await api({api:"search",q:q,suggest:1});if(token===suggestToken)renderSuggest(d,q)}catch(_){if(token===suggestToken)hideSuggest()}},160)}

function resultRow(r,exact,plausible){const item='<div class="item"><b>'+esc(r.item_name)+'</b><span>'+esc(typeLabel(r))+(plausible?' · not in current stock':' · '+esc(r.condition||"stock item")+' · '+esc(r.quantity==null?"available":r.quantity+" available"))+'</span></div>';const seller='<div class="seller"><b>'+esc(r.shop_name)+'</b><span>'+esc(placeLabel(r))+'</span></div>';const price=plausible?'<div class="price"><b>LIKELY SELLER</b><span>no current offer</span></div>':'<div class="price"><b>'+esc(money(r.asking_price))+'</b><span>'+esc(r.condition||"")+(r.quantity!=null?' · '+esc(r.quantity)+' here':'')+'</span></div>';return '<button class="row '+(exact?'exact ':'')+(plausible?'plausible':'')+'" data-shop="'+esc(r.shop_entity_id)+'" data-item="'+esc(r.item_id)+'">'+item+seller+price+'</button>'}
function bindRows(root){root.querySelectorAll("[data-shop]").forEach(b=>b.onclick=()=>{const o=(state.data.offers||[]).find(x=>String(x.shop_entity_id)===b.dataset.shop&&String(x.item_id)===b.dataset.item)||null;openShop(b.dataset.shop,o)})}
function renderResults(d,q){state.data=d;state.q=q;state.item=d.active_item_id||null;const exact=Boolean(state.item);const active=exact?(d.items||[]).find(x=>String(x.item_id)===String(state.item)):null;const available=(d.offers||[]).filter(x=>x.kind==="available"),likely=(d.offers||[]).filter(x=>x.kind!=="available");$("mode").textContent=exact?"Exact catalogue item":"Broad search";$("title").textContent=(active&&active.name?active.name:q).toUpperCase();$("resultsQ").value=q;$("searchNote").textContent=exact?"CURRENT OFFERS FOR THIS EXACT CATALOGUE ITEM":"CURRENT OFFERS ACROSS "+String(d.total_matches||d.items.length)+" RELATED CATALOGUE ITEMS";$("availableTitle").textContent=exact?"WHO HAS IT":"AVAILABLE NOW";$("availableMeta").textContent=available.length+" CURRENT OFFER"+(available.length===1?"":"S");$("available").innerHTML=available.map(r=>resultRow(r,exact,false)).join("");$("likely").innerHTML=likely.map(r=>resultRow(r,exact,true)).join("");$("availableBlock").classList.toggle("hidden",!available.length);$("likelyBlock").classList.toggle("hidden",!likely.length);$("empty").classList.toggle("hidden",Boolean(available.length||likely.length));bindRows($("available"));bindRows($("likely"));show("resultsView")}
function searchUrl(q,item){const u=new URL(location.href);u.search="";u.searchParams.set("q",q);if(item)u.searchParams.set("item",item);return u.pathname+u.search}
async function runSearch(raw,item,push){const q=String(raw||"").trim();if(!q)return;hideSuggest();state.q=q;state.item=item||null;$("resultsQ").value=q;if(push!==false)history.pushState({q:q,item:item||null},"",searchUrl(q,item));show("resultsView");$("title").textContent=item?"LOADING ITEM…":q.toUpperCase();$("searchNote").textContent="RESOLVING NIGHT CITY OFFERS…";$("availableBlock").classList.add("hidden");$("likelyBlock").classList.add("hidden");$("empty").classList.add("hidden");try{renderResults(await api({api:"search",q:q,item_id:item||null}),q)}catch(err){$("empty").textContent="Search unavailable: "+err.message;$("empty").classList.remove("hidden")}}

async function openShop(id,focus){state.focus=focus;const s=await api({api:"shop",id:id});$("sname").textContent=s.name;$("smode").textContent=String(s.stock_mode||"").replaceAll("_"," ");$("sdistrict").textContent=s.district||"Night City";$("stype").textContent=s.type||s.primary_archetype||"Commercial place";$("snote").textContent=s.blurb||s.copy||s.modelling_note||"Canonical Vend-R commercial profile.";$("ssource").textContent=s.source_ref||"Night City 2045";$("sdeps").textContent=s.tags||"—";const rows=s.stock||[];$("stock").innerHTML=rows.length?'<div class="k" style="margin-top:20px">Current stock</div>'+rows.map(r=>'<div class="stock-row '+(focus&&String(r.item_id)===String(focus.item_id)?"focus":"")+'"><div><b>'+esc(r.name)+'</b><small>'+esc([r.assortment_role,r.condition].filter(Boolean).join(" · "))+'</small></div><div class="qty">'+esc(r.quantity==null?"available":r.quantity+" here")+'</div><div class="ask">'+esc(money(r.asking_price))+'</div></div>').join(""):"";$("children").innerHTML=s.child_places&&s.child_places.length?'<div class="k" style="margin-top:20px">Contained sellers / places</div>'+s.child_places.map(c=>'<button data-child="'+esc(c.child_entity_id)+'">'+esc(c.child_name)+'</button>').join(""):"";$("children").querySelectorAll("[data-child]").forEach(b=>b.onclick=()=>openShop(b.dataset.child,null));show("shopView")}

$("homeQ").addEventListener("input",x=>queueSuggest(x.currentTarget.value));
$("homeQ").addEventListener("keydown",x=>{if(x.key==="Escape")hideSuggest()});
$("homeForm").onsubmit=x=>{x.preventDefault();runSearch($("homeQ").value,null,true)};
$("resultsForm").onsubmit=x=>{x.preventDefault();runSearch($("resultsQ").value,null,true)};
$("homeBack").onclick=()=>{history.pushState({},"",location.pathname);show("home")};
$("shopBack").onclick=()=>show("resultsView");
document.addEventListener("click",x=>{if(!$("homeForm").contains(x.target)&&!$("suggest").contains(x.target))hideSuggest()});
window.addEventListener("popstate",()=>{const p=new URLSearchParams(location.search),q=p.get("q"),item=p.get("item");if(q)runSearch(q,item,false);else show("home")});
health();
const initial=new URLSearchParams(location.search);if(initial.get("q"))runSearch(initial.get("q"),initial.get("item"),false);
</script>
</body>
</html>`

Deno.serve(async(req:Request)=>{
  if(req.method==='OPTIONS') return new Response('ok',{headers:JH});
  try{
    const u=new URL(req.url), a=u.searchParams.get('api');
    if(a==='health') return await health();
    if(a==='shops') return await shops();
    if(a==='search') return await search(u);
    if(a==='shop') return await shop(u);
    if(a==='purchase') return await purchase(req);
    if(a==='debug-item'){const all=await catalogue();return out(all[0]||null)}
    return new Response(HTML,{headers:{'content-type':'text/html; charset=utf-8'}});
  }catch(e){return out({error:e instanceof Error?e.message:String(e)},500)}
});