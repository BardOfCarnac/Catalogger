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
function textHit(i:any,terms:any[]){const n=String(i?.name||'').toLowerCase();return (terms||[]).some(t=>n.includes(String(t).toLowerCase()))}
function ruleAllows(p:any,i:any,classMap:Map<string,any>,mfrMap:Map<string,string[]>){
  const rule=matchRule(p);
  if(!rule) return {allow:true,boost:0};
  if(rule.strategy==='no_catalog_stock') return {allow:false,boost:0};
  const d=department(i,classMap), sub=String(classification(i,classMap)?.source_subcategory||'');
  if(rule.strategy==='used_specialist' && quantityClass(i,classMap)==='continuous' && rule.allow_continuous!==true) return {allow:false,boost:0};
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
  const strategy=String(matchRule(p)?.strategy||'');
  if(strategy==='event_market'&&!pri.length&&!sec.length){
    if(!d||['housing-property','services-entertainment'].includes(d)) return null;
    s=70;
  }else if(d&&pri.includes(d)) s=100; else if(d&&sec.includes(d)) s=55; else if(d) return null; else s=15;
  const max=Number(matchRule(p)?.max_base_price_eb??p.max_base_price_eb), price=basePrice(i);
  if(Number.isFinite(max)&&max>0&&price!==null&&price>max) return null;
  if(p.breadth_profile==='broad') s+=10;
  if(p.assignment_confidence==='HIGH') s+=5;
  const rule=matchRule(p)||{};
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
function stockCondition(p:any,i:any,cycle:number,classMap?:Map<string,any>){
  if(classMap&&quantityClass(i,classMap)==='continuous')return 'not_applicable';
  const options=matchRule(p)?.allowed_conditions;
  if(!Array.isArray(options)||!options.length)return 'new';
  return options[stableIndex('condition|'+cycle+'|'+p.entity_id+'|'+i.id,options.length)];
}
function stockFor(p:any,all:any[],classMap:Map<string,any>,mfrMap:Map<string,string[]>,stockGeneration=0){
  if(!['DIRECT_SELLER','EVENT_MARKET','HYBRID_DIRECT_EVENT'].includes(String(p.stock_mode||''))) return [];
  const generation=Math.max(0,Math.floor(Number(stockGeneration)||0)),plan=assortmentPlan(p);
  const ranked=all.map((item:any)=>({item,fit:score(p,item,classMap,mfrMap)}))
    .filter((x:any)=>x.fit!==null);
  const chosen=selectAssortment(p,ranked,plan,classMap,generation);
  return chosen.map((x:any)=>({
    item_id:String(x.item.id),
    name:x.item.name,
    quantity:cycleQuantity(p,x.item,classMap,x.role,generation),
    target_quantity:cycleQuantity(p,x.item,classMap,x.role,generation),
    quantity_profile:quantityClass(x.item,classMap),
    condition:stockCondition(p,x.item,generation,classMap),
    asking_price:cyclePrice(p,x.item,generation),
    visibility:'public',
    status:'in_stock',
    assortment_role:x.role,
    primary_department:department(x.item,classMap),
    relation_key:relationKey(x.item,classMap),
    price_tier:availabilityInfo(x.item).tier,
    availability_band:availabilityInfo(x.item).key,
    availability_label:availabilityInfo(x.item).label,
    availability_rank:availabilityInfo(x.item).rank,
    fit_score:x.fit,
    stock_cycle:generation,
    observation_generation:generation,
    last_change:null
  }));
}
const LAZY_STOCK_VERSION='lazy-1.1-availability';
function turnoverChance(p:any){
  const t=String(lifecycle(p)?.turnover||'steady');
  const m:any={fast:.045,steady:.030,irregular:.040,slow:.015,volatile:.060};
  return m[t]??.030;
}
function visibleStock(rows:any[]){
  return (rows||[]).filter((row:any)=>row.quantity==null||Number(row.quantity)>0);
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
  const candidates=stockFor(p,all,classMap,mfrMap,nextGeneration);
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
    const role=String(row.assortment_role||'regular');
    const same=candidates.filter((x:any)=>String(x.assortment_role||'regular')===role&&!used.has(String(x.item_id)));
    const pool=same.length?same:candidates.filter((x:any)=>!used.has(String(x.item_id)));
    if(!pool.length)return null;
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
  const obsRows=await observationForShop(String(p.entity_id),worldKey);
  const obs=obsRows[0]||null;
  const nowMs=Date.now();

  if(!obs){
    const snapshot=initialSnapshot(p,all,classMap,mfrMap);
    const stateAt=new Date(nowMs).toISOString();
    if(snapshot.length)await saveObservation(worldKey,p,0,stateAt,snapshot);
    return {snapshot,visible:visibleStock(snapshot),generation:0,state_at:stateAt,first_observation:true,changed:false,mutations:0,elapsed_days:0};
  }

  const snapshot=Array.isArray(obs.snapshot)?obs.snapshot:[];
  const result=transitionObservedStock(p,snapshot,all,classMap,mfrMap,Number(obs.generation||0),String(obs.state_at||obs.updated_at||new Date(nowMs).toISOString()),nowMs);
  if(result.changed)await saveObservation(worldKey,p,result.generation,result.state_at,result.snapshot);
  return {...result,visible:visibleStock(result.snapshot),first_observation:false};
}

async function search(u:URL){
  const q=(u.searchParams.get('q')||'').trim();
  const activeId=u.searchParams.get('item_id');
  const suggestOnly=u.searchParams.get('suggest')==='1';
  if(!q) return out({query:q,active_item_id:null,items:[],offers:[],total_matches:0});

  const [all,classMap]=await Promise.all([catalogue(),classifications()]);
  const f=q.toLowerCase();

  // Start with literal catalogue-name matches, then expand through the
  // most relevant Catalogger classifications. A query like "pistol" should
  // expand pistol families, not every ammunition family touched by a name.
  const direct=all.filter((i:any)=>String(i.name||'').toLowerCase().includes(f));
  const qnorm=f.replace(/[^a-z0-9]+/g,' ').trim();
  const qterms=qnorm.split(/\s+/).filter(Boolean).map(t=>t==='ammo'?'ammunition':t);
  const exactDirect=direct.filter((i:any)=>String(i.name||'').trim().toLowerCase()===f);
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

  const matches=all.filter((i:any)=>{
    const name=String(i.name||'').toLowerCase();
    if(exactDirect.length) return relatedKeys.has(relationKey(i,classMap));
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
    relation_key:relationKey(i,classMap),
    price_tier:availabilityInfo(i).tier,
    availability_band:availabilityInfo(i).key,
    availability_label:availabilityInfo(i).label,
    availability_rank:availabilityInfo(i).rank
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
  const [profiles,placeRows,observationRows]=await Promise.all([
    db('vendr_stock_profiles','select=*&order=name.asc'),
    db('vendr_places','select=entity_id,parent_name,district,spatial_mode'),
    db('vendr_stock_observations','select=entity_id,generation,state_at,snapshot&world_key=eq.public-2045')
  ]);
  const placeMap=new Map(placeRows.map((r:any)=>[String(r.entity_id),r]));
  const observationMap=new Map(observationRows.map((r:any)=>[String(r.entity_id),r]));
  const offerItems=active?[active]:matches;
  const stockCache=new Map<string,any[]>();
  const offers:any[]=[];

  for(const item of offerItems){
    const itemId=String(item.id);
    for(const p of profiles){
      const fit=score(p,item,classMap,mfrMap); if(fit===null) continue;
      let stock=stockCache.get(String(p.entity_id));
      if(!stock){
        const obs:any=observationMap.get(String(p.entity_id));
        const raw=obs&&Array.isArray(obs.snapshot)?obs.snapshot:initialSnapshot(p,all,classMap,mfrMap);
        stock=visibleStock(raw);
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
        condition:row?.condition??null,stock_cycle:row?.stock_cycle??null,
        price_tier:row?.price_tier??availabilityInfo(item).tier,
        availability_band:row?.availability_band??availabilityInfo(item).key,
        availability_label:row?.availability_label??availabilityInfo(item).label,
        availability_rank:row?.availability_rank??availabilityInfo(item).rank
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
  const all=await catalogue(), profiles=await db('vendr_stock_profiles','select=entity_id'), places=await db('vendr_places','select=entity_id');
  return out({ok:true,service:'vend-r-supabase',catalog_items:all.length,profiles:profiles.length,places:places.length,read_only:true,stock_model:LAZY_STOCK_VERSION});
}
async function stockAudit(){
  const [all,classMap,mfrMap,profiles]=await Promise.all([
    catalogue(),classifications(),manufacturers(),db('vendr_stock_profiles','select=*&order=name.asc')
  ]);
  const owners=profiles.filter((p:any)=>['DIRECT_SELLER','EVENT_MARKET','HYBRID_DIRECT_EVENT'].includes(String(p.stock_mode||'')));
  const rows=owners.map((p:any)=>{
    const plan=assortmentPlan(p);
    const stock=initialSnapshot(p,all,classMap,mfrMap);
    const deps:any={}, availability:any={};
    for(const row of stock){
      const d=String(row.primary_department||'other');
      deps[d]=(deps[d]||0)+1;
      const a=String(row.availability_band||'common');
      availability[a]=(availability[a]||0)+1;
    }
    return {
      entity_id:p.entity_id,name:p.name,district:p.district,stock_mode:p.stock_mode,
      archetype:p.primary_archetype,planned:plan.total,generated:stock.length,
      availability_context:availabilityContext(p),
      departments:deps,availability
    };
  });
  const catalogueAvailability:any={};
  for(const item of all){
    const a=availabilityInfo(item).key;
    catalogueAvailability[a]=(catalogueAvailability[a]||0)+1;
  }
  return out({
    stock_model:LAZY_STOCK_VERSION,
    owners:rows.length,
    zero_count:rows.filter((r:any)=>r.generated===0).length,
    underfilled_count:rows.filter((r:any)=>r.generated>0&&r.generated<Math.max(3,Math.floor(r.planned*.5))).length,
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
function planFor(p:any){
  const mode=String(p.stock_mode||'');
  const owns=['DIRECT_SELLER','EVENT_MARKET','HYBRID_DIRECT_EVENT'].includes(mode);
  return {stock_mode:mode,owns_stock:owns,action:owns?'read_profile':mode==='AGGREGATE_CONTAINER'?'delegate_to_children':'no_static_inventory'};
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
async function shops(){
  const [placeRows,profileRows]=await Promise.all([
    db('vendr_places','select=*&order=district.asc,display_name.asc'),
    db('vendr_stock_profiles','select=*&order=district.asc,name.asc')
  ]);
  const profileById=new Map(profileRows.map((p:any)=>[String(p.entity_id),p]));
  const placeIds=new Set(placeRows.map((p:any)=>String(p.entity_id)));
  const rows=placeRows.map((place:any)=>{
    const profile=profileById.get(String(place.entity_id));
    return profile?listingFromProfile(profile,place):listingFromPlace(place);
  });
  for(const profile of profileRows){
    if(!placeIds.has(String(profile.entity_id))) rows.push(listingFromProfile(profile,null));
  }
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
  const id=u.searchParams.get('id'); if(!id) return out({error:'missing id'},400);
  const [profileRows,placeRows,edges,visualRows]=await Promise.all([
    db('vendr_stock_profiles','select=*&entity_id=eq.'+encodeURIComponent(id)),
    db('vendr_places','select=*&entity_id=eq.'+encodeURIComponent(id)),
    db('vendr_parent_child_edges','select=child_entity_id,child_name,relation_type&parent_entity_id=eq.'+encodeURIComponent(id)),
    db('vendr_visual_profiles','select=*&entity_id=eq.'+encodeURIComponent(id))
  ]);
  const profile=profileRows[0]||null;
  const place=placeRows[0]||null;
  if(!profile&&!place) return out({error:'not found'},404);

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
    stock=resolved.visible;
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
    entity_level:place?.entity_level||profile?.entity_level||null,commercial_role:place?.commercial_role||null,
    stock_profile_present:Boolean(profile),stock_mode:profile?.stock_mode||'PLACE_ONLY',plan:planFor(base),
    type,tags,
    copy:profile?.data?.blurb||profile?.data?.short_description||profile?.modelling_note||placeCopy,
    short_description:profile?.data?.short_description||profile?.modelling_note||placeCopy,
    blurb:profile?.data?.blurb||profile?.data?.short_description||profile?.modelling_note||placeCopy,
    shop_scale:profile?.data?.shop_scale||null,scale_basis:profile?.data?.scale_basis||null,
    assortment:profile?.data?.assortment||null,stock_lifecycle:profile?.data?.stock_lifecycle||null,
    other:profile?.data?.other||null,owner:profile?.data?.owner||null,display_tags:display,
    modelling_note:profile?.modelling_note||'',children:edges.map((e:any)=>e.child_entity_id),
    child_places:edges,event_id:null,materialized:false,stock,
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
    trusted_stock_note:profile?.data?.catalog_match?.strategy==='tiered'?'Additional stock may be available to trusted customers.':null
  });
}


const HTML="<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n<title>Vend-R · Night City Market</title>\n<style>\n:root{\n  /* -------- LOCKED THEME -------- */\n  --rear-1:#df4a0f;   /* deepest orange */\n  --rear-2:#f57b0c;   /* tangerine */\n  --rear-3:#eea81a;   /* amber */\n  --rear-4:#f4d246;   /* yellow field */\n\n  --front-1:#f05b13;\n  --front-2:#f47b10;\n  --front-3:#eda315;\n\n  --cream:#fff6df;\n  --paper:#fffaf0;\n  --ink:#17110c;\n  --muted:#6d625a;\n  --rule:rgba(23,17,12,.32);\n\n  --panel-border:3px solid var(--ink);\n  --hero-border:4px solid var(--ink);\n  --shadow:11px 11px 0 rgba(0,0,0,.13);\n  --hero-shadow:15px 15px 0 rgba(0,0,0,.15);\n\n  --slant:95vw;\n  --band-step:38vw;\n  --band-period:204vw;\n  --bg-band-width:133vw;\n  --bg-yellow-width:185vw;\n\n  --fg-start:135vw;\n  --fg-end:-360vw;\n  --bg-base:-99.5vw;\n}\n*{box-sizing:border-box}\nhtml{background:var(--rear-4)}\nbody{\n  margin:0;\n  min-height:100vh;\n  background:var(--rear-4);\n  color:var(--ink);\n  font-family:Arial,Helvetica,sans-serif;\n}\nbutton,input{font:inherit}\n\n/* -------- BACKGROUND FIELD -------- */\n.background{\n  position:fixed;\n  inset:0;\n  z-index:0;\n  overflow:hidden;\n  background:var(--rear-4);\n}\n.bg-train{\n  position:absolute;\n  inset:0 auto 0 0;\n  width:5000vw;\n  will-change:transform;\n}\n.bg-period{\n  position:absolute;\n  top:0;\n  width:var(--band-period);\n  height:100%;\n}\n.bg-band{\n  position:absolute;\n  top:-16vh;\n  height:132vh;\n  width:var(--bg-band-width);\n  clip-path:polygon(var(--slant) 0,100% 0,var(--band-step) 100%,0 100%);\n}\n.bg-band.one{left:0;background:var(--rear-1)}\n.bg-band.two{left:38vw;background:var(--rear-2)}\n.bg-band.three{left:76vw;background:var(--rear-3)}\n.bg-band.four{\n  left:114vw;\n  width:var(--bg-yellow-width);\n  clip-path:polygon(var(--slant) 0,100% 0,90vw 100%,0 100%);\n  background:var(--rear-4);\n}\n.background:after{\n  content:\"\";\n  position:absolute;\n  inset:0;\n  pointer-events:none;\n  background:\n    radial-gradient(circle at 15% 14%, rgba(255,255,255,.14), transparent 18%),\n    radial-gradient(circle at 78% 20%, rgba(255,255,255,.09), transparent 18%);\n}\n\n/* -------- GLOBAL APP FRAME -------- */\n.app{position:relative;z-index:10}\n.view{display:none}\n.view.active{display:block}\n.shell{\n  width:min(1180px, calc(100% - 28px));\n  margin:0 auto;\n  padding:18px 0 46px;\n}\n.topbar{\n  display:grid;\n  grid-template-columns:auto 1fr auto;\n  align-items:center;\n  gap:12px;\n  margin-bottom:14px;\n}\n.brand{\n  font-weight:1000;\n  font-size:clamp(28px,4vw,44px);\n  letter-spacing:-.07em;\n  line-height:.8;\n}\n.brand small{\n  display:block;\n  margin-top:7px;\n  font:9px ui-monospace,SFMono-Regular,Menlo,monospace;\n  letter-spacing:.12em;\n  text-transform:uppercase;\n}\n.inline-search{\n  position:relative;\n  height:46px;\n  border:3px solid var(--ink);\n  background:rgba(255,250,240,.95);\n  display:flex;\n  align-items:center;\n}\n.search-suggest{\n  position:absolute;\n  z-index:300;\n  top:calc(100% + 7px);\n  left:-3px;\n  right:-3px;\n  border:3px solid var(--ink);\n  background:var(--paper);\n  max-height:min(62vh,520px);\n  overflow-y:scroll;\n  overflow-x:hidden;\n  scrollbar-width:auto;\n  scrollbar-color:var(--front-1) var(--cream);\n}\n.search-suggest::-webkit-scrollbar{width:13px}\n.search-suggest::-webkit-scrollbar-track{\n  background:var(--cream);\n  border-left:2px solid var(--ink);\n}\n.search-suggest::-webkit-scrollbar-thumb{\n  background:var(--front-1);\n  border:2px solid var(--ink);\n}\n.search-suggest[hidden]{display:none}\n.suggest-head{\n  padding:8px 11px;\n  border-bottom:2px solid var(--ink);\n  background:var(--cream);\n  color:var(--muted);\n  font:900 8px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n  letter-spacing:.08em;\n}\n.suggest-row{\n  width:100%;\n  border:0;\n  border-bottom:1px solid var(--rule);\n  background:transparent;\n  color:var(--ink);\n  padding:10px 11px;\n  text-align:left;\n  cursor:pointer;\n}\n.suggest-row:last-child{border-bottom:0}\n.suggest-row:hover,.suggest-row.active{background:rgba(244,210,70,.22)}\n.suggest-row strong{\n  display:block;\n  font-size:14px;\n  line-height:1;\n  text-transform:uppercase;\n}\n.suggest-row span{\n  display:block;\n  margin-top:4px;\n  color:var(--muted);\n  font:800 8px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n}\n.suggest-row.search-all{\n  background:var(--rear-4);\n  border-top:2px solid var(--ink);\n}\n.search-page-hero{\n  padding:22px 24px 24px;\n}\n.search-page-hero .hero-title{\n  margin-bottom:12px;\n  font-size:clamp(42px,7.5vw,88px);\n}\n.search-page-copy{\n  max-width:760px;\n  color:var(--muted);\n  font-size:14px;\n  line-height:1.45;\n}\n.search-page-form{\n  display:grid;\n  grid-template-columns:minmax(0,1fr) auto;\n  margin-top:18px;\n  border:4px solid var(--ink);\n  background:var(--paper);\n}\n.search-page-form input{\n  min-width:0;\n  border:0;\n  outline:0;\n  background:transparent;\n  padding:0 16px;\n  min-height:58px;\n  color:var(--ink);\n  font:900 17px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n}\n.search-page-form button{\n  border:0;\n  border-left:4px solid var(--ink);\n  padding:0 18px;\n  background:var(--front-1);\n  color:#fff;\n  font:1000 11px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n  cursor:pointer;\n}\n.search-empty{\n  margin-top:18px;\n  border:4px solid var(--ink);\n  background:var(--cream);\n  box-shadow:var(--shadow);\n  padding:22px;\n  font-weight:900;\n  text-transform:uppercase;\n}\n@media(max-width:520px){\n  .search-page-form{grid-template-columns:1fr}\n  .search-page-form button{min-height:44px;border-left:0;border-top:4px solid var(--ink)}\n  .search-suggest{\n    max-height:195px;\n    scrollbar-gutter:stable;\n  }\n  .suggest-head{min-height:27px}\n  .suggest-row{\n    min-height:56px;\n    padding-top:9px;\n    padding-bottom:9px;\n  }\n}\n.inline-search input{\n  width:100%;\n  height:100%;\n  border:0;\n  outline:0;\n  background:transparent;\n  padding:0 14px;\n  color:var(--ink);\n  font:700 13px ui-monospace,SFMono-Regular,Menlo,monospace;\n}\n.action-btn{\n  height:46px;\n  border:3px solid var(--ink);\n  background:var(--cream);\n  padding:0 14px;\n  color:var(--ink);\n  font:900 11px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n  cursor:pointer;\n}\n\n.hero{\n  background:var(--cream);\n  border:var(--hero-border);\n  box-shadow:var(--hero-shadow);\n  padding:26px;\n  margin-bottom:18px;\n}\n.home-hero{padding:0;overflow:hidden}\n.home-hero-grid{\n  display:grid;\n  grid-template-columns:minmax(0,1fr) clamp(414px,40vw,494px);\n  min-height:438px;\n  align-items:stretch;\n}\n.home-hero-copy{\n  padding:30px 28px 26px 32px;\n  display:flex;\n  flex-direction:column;\n  justify-content:space-between;\n  gap:30px;\n}\n.home-hero .hero-title{\n  max-width:720px;\n  margin-bottom:22px;\n  font-size:clamp(46px,6.8vw,88px);\n}\n.home-hero .hero-copy{max-width:640px;font-size:16px}\n.hero-location-line{margin-top:0}\n\n/* Spaciel sits inside an equal cream surround. The bevel is one simple sloped frame. */\n.spaciel-aperture{\n  position:relative;\n  align-self:center;\n  justify-self:center;\n  width:calc(100% - 48px);\n  max-width:422px;\n  aspect-ratio:1/1;\n  margin:24px;\n  padding:12px;\n  background:#fff4dc;\n}\n.spaciel-cutin{\n  position:relative;\n  width:100%;\n  height:100%;\n  min-width:0;\n  min-height:0;\n  overflow:hidden;\n  border:10px solid;\n  border-color:\n    #e7dcc2\n    #fff9e9\n    #fff9e9\n    #e7dcc2;\n  background:\n    radial-gradient(circle at 58% 44%,rgba(244,210,70,.09),transparent 28%),\n    linear-gradient(145deg,#172126,#0d1215 64%,#090d0f);\n  color:#f5f0df;\n  isolation:isolate;\n}\n.spaciel-cutin:after{\n  content:\"\";\n  position:absolute;\n  inset:0;\n  pointer-events:none;\n  z-index:2;\n  box-shadow:inset 0 0 55px rgba(0,0,0,.62);\n  background:\n    linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),\n    linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px);\n  background-size:24px 24px;\n  mix-blend-mode:screen;\n}\n#spacielCanvas{\n  position:absolute;\n  inset:0;\n  width:100%;\n  height:100%;\n  z-index:1;\n}\n.spaciel-hud{\n  position:absolute;\n  z-index:3;\n  font:900 9px ui-monospace,SFMono-Regular,Menlo,monospace;\n  letter-spacing:.08em;\n  text-transform:uppercase;\n  text-shadow:0 1px 2px #000;\n}\n.spaciel-topline{\n  top:22px;left:22px;right:22px;\n  display:flex;justify-content:space-between;align-items:center;\n  padding-bottom:9px;border-bottom:1px solid rgba(255,246,223,.35);\n}\n.spaciel-topline strong{font-size:12px;letter-spacing:.16em}\n.spaciel-topline span{color:#f4d246}\n.spaciel-place{top:60px;left:22px;color:#c9d2cf;line-height:1.25}\n.spaciel-place strong{color:#fff6df;font-size:14px}\n.spaciel-readout{\n  left:22px;bottom:22px;\n  color:#f4d246;\n}\n.spaciel-powered{\n  right:22px;bottom:22px;color:#aab6b2;text-align:right;\n}\n.spaciel-powered strong{color:#fff6df}\n\n.kicker{\n  font:10px ui-monospace,SFMono-Regular,Menlo,monospace;\n  color:#a73c20;\n  text-transform:uppercase;\n  letter-spacing:.14em;\n}\n.hero-title{\n  margin:8px 0 18px;\n  font-size:clamp(48px,8vw,100px);\n  line-height:.8;\n  letter-spacing:-.07em;\n  text-transform:uppercase;\n}\n.hero-title.vendor{\n  font-size:clamp(43px,7.6vw,88px);\n  line-height:.82;\n}\n.hero-copy{\n  max-width:760px;\n  margin:0;\n  color:var(--muted);\n  font-size:15px;\n  line-height:1.48;\n}\n.hero-meta{\n  display:flex;\n  flex-wrap:wrap;\n  gap:8px;\n  margin:14px 0 18px;\n}\n.tag{\n  border:2px solid var(--ink);\n  background:var(--paper);\n  padding:7px 9px 6px;\n  font:900 10px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n}\n.tag.yellow{background:var(--rear-4)}\n.tag.orange{background:var(--front-1); color:#fff}\n.hero-search{\n  border:4px solid var(--ink);\n  background:var(--paper);\n  min-height:68px;\n  display:grid;\n  grid-template-columns:1fr auto;\n}\n.hero-search input{\n  min-width:0;\n  border:0;\n  outline:0;\n  background:transparent;\n  color:var(--ink);\n  padding:0 18px;\n  font:900 clamp(15px,2.2vw,23px) ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n}\n.hero-search button{\n  border:0;\n  border-left:4px solid var(--ink);\n  background:var(--front-1);\n  color:#fff;\n  padding:0 22px;\n  font:1000 12px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n}\n.nearby-line{\n  display:flex;\n  flex-wrap:wrap;\n  gap:8px 14px;\n  align-items:center;\n  margin-top:13px;\n  font:900 10px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n}\n.token{\n  border:2px solid var(--ink);\n  background:var(--rear-4);\n  padding:7px 9px;\n}\n.muted{color:var(--muted)}\n\n/* -------- PANELS -------- */\n.grid-2{\n  display:grid;\n  grid-template-columns:1fr 1fr;\n  gap:18px;\n}\n.grid-wide{grid-column:1/-1}\n.vendor-layout{\n  display:grid;\n  grid-template-columns:minmax(0,1.75fr) minmax(280px,.72fr);\n  gap:18px;\n}\n.side-stack{\n  display:grid;\n  gap:18px;\n}\n.panel{\n  background:var(--cream);\n  border:var(--panel-border);\n  box-shadow:var(--shadow);\n}\n.section-head{\n  display:flex;\n  justify-content:space-between;\n  align-items:end;\n  gap:12px;\n  padding:15px 17px 12px;\n  border-bottom:3px solid var(--ink);\n}\n.section-head h2{\n  margin:0;\n  font-size:clamp(24px,3vw,36px);\n  line-height:.9;\n  letter-spacing:-.045em;\n  text-transform:uppercase;\n}\n.section-head span{\n  color:var(--muted);\n  text-align:right;\n  font:9px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n}\n.list-row{\n  width:100%;\n  border:0;\n  border-bottom:1px solid var(--rule);\n  background:rgba(255,250,240,.42);\n  color:var(--ink);\n  text-align:left;\n  display:grid;\n  grid-template-columns:minmax(0,1fr) auto;\n  gap:12px;\n  align-items:center;\n  padding:15px 17px;\n  cursor:pointer;\n}\n.list-row:last-child{border-bottom:0}\n.list-row:hover{background:rgba(255,255,255,.38)}\n.row-title{\n  font-weight:1000;\n  font-size:18px;\n  line-height:1;\n  text-transform:uppercase;\n}\n.row-sub{\n  margin-top:5px;\n  color:var(--muted);\n  font:10px ui-monospace,SFMono-Regular,Menlo,monospace;\n  line-height:1.35;\n  text-transform:uppercase;\n}\n.row-status{\n  min-width:92px;\n  border:2px solid var(--ink);\n  background:var(--rear-4);\n  padding:8px 9px;\n  text-align:center;\n  font:900 9px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n}\n.row-status.orange{background:var(--front-1); color:#fff}\n.row-status.amber{background:var(--rear-3)}\n\n.cards-3{\n  display:grid;\n  grid-template-columns:repeat(3,1fr);\n}\n.mini-card{\n  padding:17px;\n  min-height:148px;\n  background:rgba(255,250,240,.38);\n  border-right:1px solid var(--rule);\n}\n.mini-card:last-child{border-right:0}\n.mini-time{\n  font:900 9px ui-monospace,SFMono-Regular,Menlo,monospace;\n  color:#a73c20;\n  text-transform:uppercase;\n}\n.mini-card h3{\n  margin:6px 0 8px;\n  font-size:22px;\n  line-height:.95;\n  text-transform:uppercase;\n}\n.mini-card p{\n  margin:0;\n  color:var(--muted);\n  font-size:12px;\n  line-height:1.4;\n}\n.mini-dist{\n  margin-top:12px;\n  padding-top:9px;\n  border-top:2px solid var(--ink);\n  font:900 9px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n}\n\n\n/* -------- ITEM-SEARCH ARRIVAL -------- */\n.offer-focus{\n  margin-bottom:18px;\n  border:4px solid var(--ink);\n  background:var(--cream);\n  box-shadow:var(--shadow);\n  padding:16px 18px 17px;\n}\n.offer-focus[hidden]{display:none}\n.offer-focus-row{\n  display:grid;\n  grid-template-columns:minmax(0,1fr) auto;\n  gap:18px;\n  align-items:end;\n}\n.offer-focus h1{\n  margin:5px 0 0;\n  font-size:clamp(34px,6.6vw,72px);\n  line-height:.86;\n  letter-spacing:-.025em;\n  text-transform:uppercase;\n}\n.offer-readout{\n  min-width:132px;\n  text-align:right;\n}\n.offer-readout strong{\n  display:block;\n  font:1000 clamp(20px,3.5vw,34px) ui-monospace,SFMono-Regular,Menlo,monospace;\n}\n.offer-readout span,\n.offer-sub{\n  display:block;\n  margin-top:5px;\n  color:var(--muted);\n  font:900 9px ui-monospace,SFMono-Regular,Menlo,monospace;\n  letter-spacing:.08em;\n  text-transform:uppercase;\n}\n.stock-row{padding:10px 16px}\n.stock-name{\n  font-size:23px;\n  line-height:.98;\n  letter-spacing:-.012em;\n}\n.stock-sub{font-size:11px;line-height:1.25;margin-top:4px}\n.stock-meta{font-size:11px;line-height:1.28}\n.stock-meta strong{font-size:14px}\n.stock-name.related{\n  color:var(--front-2);\n  -webkit-text-stroke:1.9px var(--ink);\n  paint-order:stroke fill;\n  text-shadow:.8px .8px 0 var(--ink);\n}\n.stock-name.exact{\n  color:var(--rear-2);\n  -webkit-text-stroke:2.1px var(--ink);\n  paint-order:stroke fill;\n  text-shadow:1px 1px 0 var(--ink);\n  animation:vendrFocus 2.5s cubic-bezier(.22,.72,.18,1);\n}\n@keyframes vendrFocus{\n  0%,100%{color:var(--rear-2)}\n  40%,68%{color:var(--rear-4)}\n}\n.stock-row.exact-row{background:rgba(244,210,70,.14)}\n.stock-row.related-row{background:rgba(244,123,16,.06)}\n@media (max-width:760px){\n  .offer-focus-row{grid-template-columns:1fr}\n  .offer-readout{text-align:left}\n}\n\n\n/* -------- SEARCH RESULT OFFERS -------- */\n.search-offer-section{\n  margin-top:18px;\n  border:4px solid var(--ink);\n  background:var(--cream);\n  box-shadow:var(--shadow);\n}\n.search-offer-head{\n  display:flex;\n  justify-content:space-between;\n  gap:14px;\n  align-items:end;\n  padding:12px 14px 10px;\n  border-bottom:3px solid var(--ink);\n}\n.search-offer-head h2{\n  margin:0;\n  font-size:24px;\n  line-height:.95;\n  text-transform:uppercase;\n}\n.search-offer-head span{\n  color:var(--muted);\n  font:900 9px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n  text-align:right;\n}\n.search-offer-list{display:grid}\n.search-offer{\n  width:100%;\n  border:0;\n  border-bottom:1px solid var(--rule);\n  background:rgba(255,250,240,.56);\n  color:var(--ink);\n  display:grid;\n  grid-template-columns:minmax(0,1.45fr) minmax(0,1fr) auto;\n  gap:14px;\n  align-items:center;\n  padding:11px 14px;\n  text-align:left;\n  cursor:pointer;\n}\n.search-offer:last-child{border-bottom:0}\n.search-offer:hover{background:rgba(244,210,70,.14)}\n.search-offer .item-name,\n.search-offer .seller-name{\n  display:block;\n  font-size:20px;\n  line-height:1;\n  font-weight:1000;\n  text-transform:uppercase;\n}\n.search-offer .seller-name{font-size:17px}\n.search-offer .item-meta,\n.search-offer .place-meta,\n.search-offer .price-meta{\n  display:block;\n  margin-top:4px;\n  color:var(--muted);\n  font:900 9px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n  letter-spacing:.05em;\n}\n.search-offer .price-block{\n  min-width:104px;\n  text-align:right;\n}\n.search-offer .price{\n  display:block;\n  font:1000 20px ui-monospace,SFMono-Regular,Menlo,monospace;\n}\n.search-offer.plausible .price{\n  font-size:11px;\n  color:var(--muted);\n}\n.search-offer.exact-mode{\n  grid-template-columns:minmax(0,1fr) auto;\n}\n.search-offer.exact-mode .item-col{display:none}\n@media(max-width:700px){\n  .search-offer{\n    grid-template-columns:minmax(0,1fr) auto;\n  }\n  .search-offer .seller-col{grid-column:1}\n  .search-offer .price-block{grid-column:2;grid-row:1 / span 2}\n  .search-offer.exact-mode{grid-template-columns:minmax(0,1fr) auto}\n}\n\n\n/* -------- NEARBY SEARCH PAGE -------- */\n.search-nearby-hero{padding:0;overflow:hidden}\n.search-nearby-grid{\n  display:grid;\n  grid-template-columns:minmax(0,1.2fr) clamp(370px,38vw,470px);\n  min-height:430px;\n  align-items:stretch;\n}\n.search-nearby-copy{\n  padding:27px 25px 24px 29px;\n  display:flex;\n  flex-direction:column;\n  min-width:0;\n}\n.search-nearby-copy .hero-title{\n  margin:5px 0 7px;\n  font-size:clamp(42px,6.5vw,78px);\n}\n.search-query-line{\n  color:var(--muted);\n  font:900 10px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n  letter-spacing:.06em;\n  margin-bottom:13px;\n}\n.nearby-offer-list{\n  border-top:3px solid var(--ink);\n  margin-top:auto;\n}\n.nearby-offer{\n  width:100%;\n  border:0;\n  border-bottom:1px solid var(--rule);\n  background:transparent;\n  color:var(--ink);\n  display:grid;\n  grid-template-columns:minmax(0,1fr) auto;\n  gap:12px;\n  align-items:center;\n  padding:10px 0;\n  text-align:left;\n  cursor:pointer;\n}\n.nearby-offer:last-child{border-bottom:0}\n.nearby-offer:hover{background:rgba(244,210,70,.12)}\n.nearby-offer strong{\n  display:block;\n  font-size:16px;\n  line-height:1;\n  text-transform:uppercase;\n}\n.nearby-offer span{\n  display:block;\n  margin-top:4px;\n  color:var(--muted);\n  font:900 8px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n}\n.nearby-offer .nearby-price{\n  margin:0;\n  min-width:82px;\n  text-align:right;\n  color:var(--ink);\n  font-size:15px;\n}\n.search-location-card{\n  position:relative;\n  align-self:center;\n  justify-self:center;\n  width:calc(100% - 48px);\n  max-width:410px;\n  aspect-ratio:1/1;\n  margin:24px;\n  padding:12px;\n  background:#fff4dc;\n}\n.search-location-card .spaciel-cutin{height:100%}\n.search-location-label{\n  position:absolute;\n  z-index:4;\n  left:22px;\n  right:22px;\n  bottom:54px;\n  border:2px solid rgba(255,246,223,.72);\n  background:rgba(12,17,20,.78);\n  padding:9px 10px;\n  color:#fff6df;\n}\n.search-location-label span{\n  display:block;\n  color:#c9d2cf;\n  font:800 8px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n}\n.search-location-label strong{\n  display:block;\n  margin-top:3px;\n  font-size:16px;\n  text-transform:uppercase;\n}\n.search-location-label small{\n  display:block;\n  margin-top:3px;\n  color:#f4d246;\n  font:800 8px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n}\n.results-sort{\n  display:flex;\n  flex-wrap:wrap;\n  gap:6px;\n  padding:10px 14px;\n  border-bottom:2px solid var(--ink);\n  background:rgba(255,250,240,.45);\n}\n.results-sort button{\n  border:2px solid var(--ink);\n  background:var(--paper);\n  padding:6px 8px;\n  color:var(--ink);\n  font:900 8px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n  cursor:pointer;\n}\n.results-sort button.on{background:var(--rear-4)}\n.related-items{\n  display:grid;\n  grid-template-columns:repeat(3,minmax(0,1fr));\n}\n.related-item{\n  border:0;\n  border-right:1px solid var(--rule);\n  background:rgba(255,250,240,.42);\n  padding:15px;\n  text-align:left;\n  color:var(--ink);\n  cursor:pointer;\n}\n.related-item:last-child{border-right:0}\n.related-item:hover{background:rgba(244,210,70,.14)}\n.related-item strong{\n  display:block;\n  font-size:17px;\n  line-height:1;\n  text-transform:uppercase;\n}\n.related-item span{\n  display:block;\n  margin-top:5px;\n  color:var(--muted);\n  font:900 8px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n}\n@media(max-width:760px){\n  .search-nearby-grid{grid-template-columns:1fr}\n  .search-location-card{width:calc(100% - 36px);margin:0 18px 18px}\n  .related-items{grid-template-columns:1fr}\n  .related-item{border-right:0;border-bottom:1px solid var(--rule)}\n  .related-item:last-child{border-bottom:0}\n}\n\n/* -------- VENDOR PAGE -------- */\n.vendor-hero{\n  padding:0;\n  overflow:hidden;\n}\n.vendor-photo-strip{\n  position:relative;\n  min-height:245px;\n  padding:25px 27px 22px;\n  display:flex;\n  flex-direction:column;\n  justify-content:flex-end;\n  overflow:hidden;\n  background:\n    linear-gradient(90deg,rgba(23,17,12,.48) 0%,rgba(23,17,12,.22) 46%,rgba(23,17,12,.04) 100%),\n    linear-gradient(135deg,#7b6b58,#d5c8ae);\n  background-size:cover;\n  background-position:50% 50%;\n  color:var(--cream);\n}\n.vendor-photo-strip:after{\n  content:\"\";\n  position:absolute;\n  inset:0;\n  pointer-events:none;\n  background:linear-gradient(180deg,rgba(0,0,0,.015),rgba(0,0,0,.07));\n}\n.vendor-photo-content{\n  position:relative;\n  z-index:1;\n  max-width:930px;\n}\n.vendor-photo-strip .kicker{\n  color:#ffd86a;\n  text-shadow:0 1px 2px rgba(0,0,0,.7);\n}\n.vendor-photo-strip .hero-title.vendor{\n  color:var(--cream);\n  margin-bottom:17px;\n  text-shadow:0 2px 3px rgba(0,0,0,.72),0 0 10px rgba(0,0,0,.24);\n}\n.vendor-photo-strip .hero-meta{margin-bottom:0}\n.vendor-photo-strip .tag{\n  color:var(--ink);\n  text-shadow:none;\n}\n.vendor-photo-credit{\n  position:absolute;\n  right:13px;\n  bottom:10px;\n  z-index:2;\n  max-width:48%;\n  text-align:right;\n  color:rgba(255,246,223,.72);\n  font:700 8px ui-monospace,SFMono-Regular,Menlo,monospace;\n  letter-spacing:.05em;\n  text-transform:uppercase;\n}\n.vendor-photo-credit a{\n  color:inherit;\n  text-decoration:none;\n  border-bottom:1px solid rgba(255,246,223,.35);\n}\n.vendor-photo-credit a:hover{color:#fff}\n.vendor-info-body{padding:22px 27px 25px}\n.hero-columns{\n  display:grid;\n  grid-template-columns:minmax(0,1.5fr) minmax(220px,.7fr);\n  gap:22px;\n  align-items:end;\n}\n.owner{\n  border-left:4px solid var(--ink);\n  padding-left:13px;\n}\n.owner strong{\n  display:block;\n  text-transform:uppercase;\n  font-size:17px;\n}\n.owner span{\n  display:block;\n  margin-top:4px;\n  color:var(--muted);\n  font:11px ui-monospace,SFMono-Regular,Menlo,monospace;\n  line-height:1.35;\n  text-transform:uppercase;\n}\n.restock-band{\n  background:var(--rear-4);\n  border-bottom:3px solid var(--ink);\n  padding:10px 18px;\n  font:900 10px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n}\n.stock-row{\n  display:grid;\n  grid-template-columns:minmax(0,1.25fr) minmax(130px,.6fr) auto;\n  gap:14px;\n  align-items:center;\n  padding:15px 18px;\n  border-bottom:1px solid var(--rule);\n  background:rgba(255,250,240,.42);\n}\n.stock-row:last-child{border-bottom:0}\n.stock-name{\n  font-size:19px;\n  font-weight:1000;\n  line-height:1;\n  text-transform:uppercase;\n}\n.stock-sub{\n  margin-top:5px;\n  color:var(--muted);\n  font:10px ui-monospace,SFMono-Regular,Menlo,monospace;\n  line-height:1.35;\n  text-transform:uppercase;\n}\n.stock-meta{\n  font:10px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n  line-height:1.4;\n}\n.stock-meta strong{font-size:12px}\n.price{\n  min-width:88px;\n  text-align:center;\n  border:2px solid var(--ink);\n  padding:10px 9px;\n  background:var(--front-1);\n  color:#fff;\n  font:1000 16px ui-monospace,SFMono-Regular,Menlo,monospace;\n}\n.price.alt{background:var(--front-2)}\n.price.amber{background:var(--rear-3); color:var(--ink)}\n.fact-list{padding:3px 16px}\n.fact{\n  display:grid;\n  grid-template-columns:92px 1fr;\n  gap:10px;\n  padding:12px 0;\n  border-bottom:1px solid var(--rule);\n}\n.fact:last-child{border-bottom:0}\n.fact dt{\n  margin:0;\n  color:var(--muted);\n  font:9px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n}\n.fact dd{\n  margin:0;\n  font-size:14px;\n  font-weight:800;\n}\n.market-card-side{padding:17px 18px 18px}\n.market-card-side h3{\n  margin:5px 0 8px;\n  font-size:25px;\n  line-height:.95;\n  text-transform:uppercase;\n}\n.market-card-side p{\n  margin:0 0 14px;\n  color:var(--muted);\n  font-size:13px;\n  line-height:1.4;\n}\n.market-line{\n  border-top:2px solid var(--ink);\n  padding-top:10px;\n  font:900 10px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n}\n.known-grid{\n  display:grid;\n  grid-template-columns:1fr 1fr;\n  gap:7px;\n  padding:15px 16px 17px;\n}\n.known-grid span{\n  border:2px solid var(--ink);\n  background:var(--paper);\n  padding:9px;\n  font:900 9px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n  text-align:center;\n}\n\n/* -------- TEMPLATE NOTES -------- */\n.template-note{\n  margin-top:18px;\n  border:var(--panel-border);\n  background:rgba(255,246,223,.96);\n  box-shadow:var(--shadow);\n  padding:12px 14px;\n}\n.template-note h3{\n  margin:0 0 8px;\n  font-size:16px;\n  text-transform:uppercase;\n}\n.template-note ul{\n  margin:8px 0 0 18px;\n  padding:0;\n  color:var(--muted);\n  font-size:13px;\n  line-height:1.5;\n}\n\n/* -------- FOOTER -------- */\n.footer{\n  margin-top:18px;\n  border:var(--panel-border);\n  background:rgba(255,246,223,.94);\n  padding:11px 14px;\n  display:flex;\n  justify-content:space-between;\n  gap:12px;\n  font:9px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;\n}\n.footer span:last-child{text-align:right}\n\n/* -------- STINGER TRANSITION -------- */\n.stinger-layer{\n  position:fixed;\n  inset:0;\n  z-index:5000;\n  overflow:hidden;\n  pointer-events:none;\n}\n.fg-page{\n  position:absolute;\n  top:-16vh;\n  width:320vw;\n  height:132vh;\n  clip-path:polygon(var(--slant) 0,100% 0,225vw 100%,0 100%);\n  will-change:transform;\n}\n.fg-page.one{background:var(--front-1);z-index:1}\n.fg-page.two{background:var(--front-2);z-index:2}\n.fg-page.three{background:var(--front-3);z-index:3}\n\n/* -------- RESPONSIVE -------- */\n@media (max-width:920px) and (min-width:761px){\n  .home-hero-grid{grid-template-columns:minmax(0,1fr) 390px}\n  .home-hero-copy{padding:24px}\n  .home-hero .hero-title{font-size:clamp(42px,5.6vw,64px)}\n  .spaciel-aperture{width:calc(100% - 40px);margin:20px;padding:10px}\n}\n@media (max-width:760px){\n  .shell{width:min(100% - 22px,680px);padding-top:11px}\n  .topbar{grid-template-columns:1fr auto}\n  .inline-search{grid-column:1/-1;grid-row:2}\n  .grid-2,.vendor-layout{grid-template-columns:1fr}\n  .home-hero-grid{grid-template-columns:1fr}\n  .spaciel-aperture{\n    width:calc(100% - 36px);\n    margin:0 18px 18px;\n    padding:10px;\n    aspect-ratio:1/1;\n  }\n  .grid-wide{grid-column:auto}\n  .cards-3{grid-template-columns:1fr}\n  .mini-card{border-right:0;border-bottom:1px solid var(--rule)}\n  .mini-card:last-child{border-bottom:0}\n  .hero{padding:18px}\n  .hero-columns{grid-template-columns:1fr}\n  .vendor-photo-strip{min-height:205px;padding:20px 18px 18px}\n  .vendor-info-body{padding:18px}\n  .vendor-photo-credit{right:9px;bottom:8px;max-width:65%;font-size:7px}\n  .side-stack{grid-template-columns:1fr 1fr}\n  .side-stack .panel:first-child{grid-column:1/-1}\n  .stock-row{\n    grid-template-columns:1fr auto;\n    gap:10px;\n  }\n  .stock-meta{grid-column:1}\n  .price{grid-column:2;grid-row:1 / span 2}\n}\n@media (max-width:520px){\n  .hero-title{font-size:48px}\n  .home-hero-copy{padding:22px 18px}\n  .home-hero .hero-title{font-size:52px}\n  .hero-search{grid-template-columns:1fr}\n  .hero-search input{min-height:60px}\n  .hero-search button{\n    border-left:0;\n    border-top:4px solid var(--ink);\n    min-height:46px;\n  }\n  .section-head{align-items:start;flex-direction:column}\n  .section-head span{text-align:left}\n  .side-stack{grid-template-columns:1fr}\n  .side-stack .panel:first-child{grid-column:auto}\n  .footer{display:grid}\n  .footer span:last-child{text-align:left}\n}\n\n.template-note{display:none}\n.mini-card[data-shop]{cursor:pointer}\n.mini-card[data-shop]:hover{background:rgba(255,255,255,.48)}\n.action-btn[disabled]{opacity:.65;cursor:default}\n\n/* Place hierarchy: containers render child businesses in the main list. */\n.parent-location-link{\n  display:block;width:100%;margin-top:14px;padding:11px 12px;border:2px solid var(--ink);\n  background:var(--paper);color:var(--ink);text-align:left;cursor:pointer;\n}\n.parent-location-link:hover{background:var(--rear-4)}\n.parent-location-link>span,.parent-location-link>small{\n  display:block;font:900 8px ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;letter-spacing:.08em;color:var(--muted);\n}\n.parent-location-link>strong{display:block;margin:4px 0;font-size:14px;text-transform:uppercase}\n.place-row{\n  width:100%;border:0;border-bottom:1px solid var(--rule);background:rgba(255,250,240,.42);\n  display:grid;grid-template-columns:minmax(0,1fr) minmax(120px,.42fr) auto;\n  gap:14px;align-items:center;padding:15px 18px;text-align:left;color:var(--ink);cursor:pointer;\n}\n.place-row:hover{background:rgba(255,255,255,.55)}\n.place-row:last-child{border-bottom:0}\n.place-row .place-name{font-size:19px;font-weight:1000;line-height:1;text-transform:uppercase}\n.place-row .place-desc{margin-top:6px;color:var(--muted);font-size:11px;line-height:1.4}\n.place-row .place-tags{display:flex;gap:5px;flex-wrap:wrap;margin-top:8px}\n.place-row .place-tag{\n  border:1px solid var(--ink);padding:4px 6px;background:var(--paper);\n  font:900 8px ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase;\n}\n.place-row .place-meta{\n  text-align:right;font:9px/1.35 ui-monospace,SFMono-Regular,Menlo,monospace;\n  text-transform:uppercase;color:var(--muted);\n}\n.place-row .place-meta strong{display:block;color:var(--ink)}\n.place-row .place-arrow{font:1000 10px ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase}\n.stock-subsection-title{\n  padding:12px 18px;border-bottom:3px solid var(--ink);background:var(--rear-4);\n  font:1000 10px ui-monospace,SFMono-Regular,Menlo,monospace;text-transform:uppercase;letter-spacing:.07em;\n}\n@media(max-width:760px){\n  .place-row{grid-template-columns:minmax(0,1fr) auto}\n  .place-row .place-meta{grid-column:1;text-align:left}\n  .place-row .place-arrow{grid-column:2;grid-row:1/3}\n}\n\n</style>\n</head>\n<body>\n\n<div class=\"background\">\n  <div class=\"bg-train\" id=\"bgTrain\"></div>\n</div>\n\n<div class=\"app\">\n  <!-- ========== HOME TEMPLATE ========== -->\n  <section class=\"view active\" id=\"homeView\">\n    <div class=\"shell\">\n      <header class=\"topbar\">\n        <div class=\"brand\">VEND-R<small>Night City Market</small></div>\n        <label class=\"inline-search\">\n          <input id=\"marketSearchTop\" type=\"search\" placeholder=\"SEARCH THE MARKET\" autocomplete=\"off\">\n          <div class=\"search-suggest\" id=\"marketSuggest\" hidden></div>\n        </label>\n        <button class=\"action-btn\" id=\"marketBrowseButton\">Browse</button>\n      </header>\n\n      <section class=\"hero home-hero\">\n        <div class=\"home-hero-grid\">\n          <div class=\"home-hero-copy\">\n            <div>\n              <h1 class=\"hero-title\">Find what’s already out there.</h1>\n              <p class=\"hero-copy\">\n                Night City is full of places to buy, sell and trade. Vend-R brings together established shops,\n                markets, stalls and services, with stock that can change as the city does. Search above for\n                something specific, or browse below to see who is trading and what is happening around the city.\n              </p>\n            </div>\n\n            <div class=\"nearby-line hero-location-line\">\n              <span>Selected area</span>\n              <span class=\"token\">Night City</span>\n              <span class=\"muted\" id=\"marketPulse\">Connecting to Night City market data…</span>\n            </div>\n          </div>\n\n          <div class=\"spaciel-aperture\">\n            <div class=\"spaciel-cutin\" aria-label=\"Spaciel Night City market layer preview\">\n              <canvas id=\"spacielCanvas\"></canvas>\n              <div class=\"spaciel-hud spaciel-topline\">\n                <strong>SPACIEL</strong><span>MARKET LAYER</span>\n              </div>\n              <div class=\"spaciel-hud spaciel-place\">\n                NIGHT CITY<br><strong>PLACE FEED</strong>\n              </div>\n              <div class=\"spaciel-hud spaciel-readout\" id=\"spacielReadout\">CONNECTING…</div>\n              <div class=\"spaciel-hud spaciel-powered\">POWERED BY <strong>SPACIEL</strong></div>\n            </div>\n          </div>\n        </div>\n      </section>\n\n      <div class=\"grid-2\">\n        <section class=\"panel\" id=\"primarySellerPanel\">\n          <div class=\"section-head\">\n            <h2 id=\"primarySellerTitle\">Known sellers</h2>\n            <span id=\"primarySellerMeta\">Canonical commercial<br>profiles</span>\n          </div>\n\n          <button class=\"list-row js-open-vendor\">\n            <div>\n              <div class=\"row-title\">Kabuki Armature &amp; Surplus</div>\n              <div class=\"row-sub\">Tech / surplus · Kabuki · 0.8 km</div>\n            </div>\n            <div class=\"row-status\">Open<br>to 01:00</div>\n          </button>\n\n          <button class=\"list-row\">\n            <div>\n              <div class=\"row-title\">Hollowpoint Hardware</div>\n              <div class=\"row-sub\">Tools / security · Little China · 1.4 km</div>\n            </div>\n            <div class=\"row-status\">Open<br>to 23:00</div>\n          </button>\n\n          <button class=\"list-row\">\n            <div>\n              <div class=\"row-title\">Mara's Second Life</div>\n              <div class=\"row-sub\">Clothing / salvage · Kabuki · 1.7 km</div>\n            </div>\n            <div class=\"row-status\">Open<br>late</div>\n          </button>\n        </section>\n\n        <section class=\"panel\" id=\"secondarySellerPanel\">\n          <div class=\"section-head\">\n            <h2 id=\"secondarySellerTitle\">Direct sellers</h2>\n            <span id=\"secondarySellerMeta\">Likely stocked<br>places</span>\n          </div>\n\n          <button class=\"list-row js-open-vendor\">\n            <div>\n              <div class=\"row-title\">Kabuki Armature &amp; Surplus</div>\n              <div class=\"row-sub\">Basic techtools · power cells · odd optics</div>\n            </div>\n            <div class=\"row-status orange\">38 min<br>ago</div>\n          </button>\n\n          <button class=\"list-row\">\n            <div>\n              <div class=\"row-title\">Lucky Strike Autos</div>\n              <div class=\"row-sub\">Vehicle parts · tyres · roadside kits</div>\n            </div>\n            <div class=\"row-status orange\">51 min<br>ago</div>\n          </button>\n\n          <button class=\"list-row\">\n            <div>\n              <div class=\"row-title\">Neon Medic</div>\n              <div class=\"row-sub\">Medical consumables · clinic surplus</div>\n            </div>\n            <div class=\"row-status orange\">1 hr<br>ago</div>\n          </button>\n        </section>\n\n        <section class=\"panel grid-wide\" id=\"marketPanel\">\n          <div class=\"section-head\">\n            <h2 id=\"marketPanelTitle\">Markets</h2>\n            <span id=\"marketPanelMeta\">Containers / events<br>from the city graph</span>\n          </div>\n\n          <div class=\"cards-3\" id=\"marketCards\">\n            <article class=\"mini-card\">\n              <div class=\"mini-time\">20:00–01:00</div>\n              <h3>Kabuki Night Market</h3>\n              <p>Electronics, salvage, food, improvised tools and whatever arrived after dark.</p>\n              <div class=\"mini-dist\">0.4 km · 18 sellers reporting</div>\n            </article>\n\n            <article class=\"mini-card\">\n              <div class=\"mini-time\">21:30–late</div>\n              <h3>Underpass Exchange</h3>\n              <p>Small moving market with vehicle parts, ammunition, clothing and fixer tables.</p>\n              <div class=\"mini-dist\">1.9 km · location confirmed</div>\n            </article>\n\n            <article class=\"mini-card\">\n              <div class=\"mini-time\">From 22:00</div>\n              <h3>Red Lantern Pop-Up</h3>\n              <p>Food, music, cheap consumer goods and sellers who do not advertise stock.</p>\n              <div class=\"mini-dist\">2.6 km · 9 sellers reporting</div>\n            </article>\n          </div>\n        </section>\n      </div>\n\n      <div class=\"template-note\">\n        <h3>Homepage template rules</h3>\n        <ul>\n          <li>Lead with the large search ask.</li>\n          <li>Front page objects are shops, sellers, and markets — not abstract product categories.</li>\n          <li>Favour states like open now, restocked recently, and tonight.</li>\n          <li>Cards should stay cream-on-field, with dark text and orange/yellow used as status emphasis.</li>\n        </ul>\n      </div>\n\n      <footer class=\"footer\">\n        <span>Local market pulse · Watson / Kabuki</span>\n        <span>Seller supplied · availability may move</span>\n      </footer>\n    </div>\n  </section>\n\n  <!-- ========== SEARCH RESULTS ========== -->\n  <section class=\"view\" id=\"searchView\">\n    <div class=\"shell\">\n      <header class=\"topbar\">\n        <div class=\"brand\">VEND-R<small>Night City Market</small></div>\n        <form class=\"inline-search\" id=\"searchPageForm\">\n          <input id=\"searchPageInput\" type=\"search\" placeholder=\"SEARCH AGAIN\" autocomplete=\"off\">\n        </form>\n        <button class=\"action-btn\" id=\"searchBackHome\">← Market</button>\n      </header>\n\n      <section class=\"hero search-nearby-hero\">\n        <div class=\"search-nearby-grid\">\n          <div class=\"search-nearby-copy\">\n            <div class=\"kicker\" id=\"searchModeLabel\">Broad search</div>\n            <h1 class=\"hero-title\">Results nearby</h1>\n            <div class=\"search-query-line\" id=\"searchQueryLine\">Searching Night City…</div>\n            <div class=\"nearby-offer-list\" id=\"nearbyOffersList\"></div>\n          </div>\n\n          <div class=\"search-location-card\">\n            <div class=\"spaciel-cutin\" aria-label=\"Spaciel search area preview\">\n              <canvas id=\"searchSpacielCanvas\"></canvas>\n              <div class=\"spaciel-hud spaciel-topline\">\n                <strong>SPACIEL</strong><span>SEARCH AREA</span>\n              </div>\n              <div class=\"spaciel-hud spaciel-place\">\n                RESULTS<br><strong id=\"searchMapQuery\">NEARBY</strong>\n              </div>\n              <div class=\"spaciel-hud spaciel-readout\" id=\"searchSpacielReadout\">CONNECTING…</div>\n              <div class=\"search-location-label\">\n                <span>Nearby to</span>\n                <strong id=\"searchLocationName\">Night City</strong>\n                <small id=\"searchLocationMode\">City-wide · changeable later</small>\n              </div>\n              <div class=\"spaciel-hud spaciel-powered\">POWERED BY <strong>SPACIEL</strong></div>\n            </div>\n          </div>\n        </div>\n      </section>\n\n      <section class=\"search-offer-section\" id=\"availableOffersSection\" hidden>\n        <div class=\"search-offer-head\">\n          <h2>More results</h2>\n          <span id=\"availableOffersMeta\">Current stock</span>\n        </div>\n        <div class=\"results-sort\" id=\"resultsSort\">\n          <button type=\"button\" data-sort=\"location\" class=\"on\">Location</button>\n          <button type=\"button\" data-sort=\"price\">Lowest price</button>\n          <button type=\"button\" data-sort=\"condition\">Condition</button>\n          <button type=\"button\" data-sort=\"availability\">Availability</button>\n        </div>\n        <div class=\"search-offer-list\" id=\"availableOffersList\"></div>\n      </section>\n\n      <section class=\"search-offer-section\" id=\"plausibleOffersSection\" hidden>\n        <div class=\"search-offer-head\">\n          <h2>Other likely sellers</h2>\n          <span>Profile fit · not in current stock</span>\n        </div>\n        <div class=\"search-offer-list\" id=\"plausibleOffersList\"></div>\n      </section>\n\n      <section class=\"search-offer-section\" id=\"relatedItemsSection\" hidden>\n        <div class=\"search-offer-head\">\n          <h2>Related items</h2>\n          <span>Same catalogue family · compatibility links later</span>\n        </div>\n        <div class=\"related-items\" id=\"relatedItemsList\"></div>\n      </section>\n\n      <div class=\"search-empty\" id=\"searchEmpty\" hidden>No current Vend-R matches.</div>\n\n      <footer class=\"footer\">\n        <span id=\"searchFooterLeft\">Night City market search</span>\n        <span>Current stock · live seller profiles</span>\n      </footer>\n    </div>\n  </section>\n\n  <!-- ========== VENDOR TEMPLATE ========== -->\n  <section class=\"view\" id=\"vendorView\">\n    <div class=\"shell\">\n      <header class=\"topbar\">\n        <div class=\"brand\">VEND-R<small>Night City Market</small></div>\n        <label class=\"inline-search\"><input id=\"shopSearch\" type=\"search\" placeholder=\"SEARCH THIS SHOP\"></label>\n        <button class=\"action-btn\" id=\"backToMarket\">← Back</button>\n      </header>\n\n      <section class=\"offer-focus\" id=\"offerFocus\" hidden>\n        <div class=\"kicker\" id=\"offerKicker\">Current offer</div>\n        <div class=\"offer-focus-row\">\n          <h1 id=\"offerItemName\">Selected item</h1>\n          <div class=\"offer-readout\">\n            <strong id=\"offerPrice\">—</strong>\n            <span id=\"offerQuantity\">—</span>\n          </div>\n        </div>\n        <div class=\"offer-sub\" id=\"offerSub\"></div>\n      </section>\n\n      <section class=\"hero vendor-hero\">\n        <div class=\"vendor-photo-strip\" id=\"vendorPhotoStrip\">\n          <div class=\"vendor-photo-content\">\n            <div class=\"kicker\" id=\"vendorKicker\">Night City / seller profile</div>\n            <h1 class=\"hero-title vendor\" id=\"vendorName\">Seller</h1>\n\n            <div class=\"hero-meta\">\n              <span class=\"tag yellow\" id=\"vendorStatus\">Profile</span>\n              <span class=\"tag\" id=\"vendorDistrict\">Night City</span>\n              <span class=\"tag\" id=\"vendorType\">Commercial place</span>\n              <span class=\"tag orange\" id=\"vendorStockMode\">Stock model</span>\n            </div>\n          </div>\n          <div class=\"vendor-photo-credit\" id=\"vendorPhotoCredit\"></div>\n        </div>\n\n        <div class=\"vendor-info-body\">\n          <div class=\"hero-columns\">\n            <p class=\"hero-copy\" id=\"vendorCopy\">Loading seller profile…</p>\n            <div class=\"owner\">\n              <strong id=\"vendorOwnerLabel\">Vend-R record</strong>\n              <span id=\"vendorOwnerSub\">Canonical Night City commercial profile</span>\n              <button class=\"parent-location-link\" id=\"parentLocationLink\" type=\"button\" hidden>\n                <span>← Back to containing location</span>\n                <strong id=\"parentLocationName\">Containing location</strong>\n                <small>Browse the larger market / complex</small>\n              </button>\n            </div>\n          </div>\n        </div>\n      </section>\n\n      <div class=\"vendor-layout\">\n        <section class=\"panel\">\n          <div class=\"section-head\">\n            <h2 id=\"stockPanelTitle\">Stock</h2>\n            <span id=\"stockSummary\">Read-only profile<br>No shelf state yet</span>\n          </div>\n\n          <div class=\"restock-band\" id=\"restockBand\">Public preview · search does not materialize stock</div>\n\n          <div id=\"stockList\">\n            <article class=\"stock-row\" data-search=\"tool kit basic repair tools\">\n              <div>\n                <div class=\"stock-name\">Basic Techtool</div>\n                <div class=\"stock-sub\">Tools · general repair · clean stock</div>\n              </div>\n              <div class=\"stock-meta\"><strong>4 here</strong><br>restocked today</div>\n              <div class=\"price\">100eb</div>\n            </article>\n\n            <article class=\"stock-row\" data-search=\"cyberdeck case electronics carry\">\n              <div>\n                <div class=\"stock-name\">Armoured Deck Case</div>\n                <div class=\"stock-sub\">Electronics · used · cosmetic wear</div>\n              </div>\n              <div class=\"stock-meta\"><strong>1 here</strong><br>new arrival</div>\n              <div class=\"price alt\">220eb</div>\n            </article>\n\n            <article class=\"stock-row\" data-search=\"battery pack power cell rechargeable\">\n              <div>\n                <div class=\"stock-name\">Rechargeable Power Cell</div>\n                <div class=\"stock-sub\">Power · sealed pack · generic</div>\n              </div>\n              <div class=\"stock-meta\"><strong>6 here</strong><br>steady stock</div>\n              <div class=\"price\">50eb</div>\n            </article>\n\n            <article class=\"stock-row\" data-search=\"radio scanner comms communications\">\n              <div>\n                <div class=\"stock-name\">Pocket Scanner</div>\n                <div class=\"stock-sub\">Comms · second-hand · tested</div>\n              </div>\n              <div class=\"stock-meta\"><strong>2 here</strong><br>selling fast</div>\n              <div class=\"price alt\">180eb</div>\n            </article>\n\n            <article class=\"stock-row\" data-search=\"optics lens camera salvaged\">\n              <div>\n                <div class=\"stock-name\">Salvaged Optical Assembly</div>\n                <div class=\"stock-sub\">Optics · incomplete · buyer beware</div>\n              </div>\n              <div class=\"stock-meta\"><strong>1 here</strong><br>oddity</div>\n              <div class=\"price amber\">75eb</div>\n            </article>\n          </div>\n        </section>\n\n        <aside class=\"side-stack\">\n          <section class=\"panel\">\n            <div class=\"section-head\">\n              <h2>Shop state</h2>\n              <span>Live vendor record</span>\n            </div>\n            <dl class=\"fact-list\">\n              <div class=\"fact\"><dt>Status</dt><dd id=\"factStatus\">Profile only</dd></div>\n              <div class=\"fact\"><dt>District</dt><dd id=\"factDistrict\">Night City</dd></div>\n              <div class=\"fact\"><dt>Stock mode</dt><dd id=\"factStockMode\">—</dd></div>\n              <div class=\"fact\"><dt>Archetype</dt><dd id=\"factArchetype\">—</dd></div>\n              <div class=\"fact\"><dt>Source</dt><dd id=\"factSource\">—</dd></div>\n              <div class=\"fact\"><dt>World state</dt><dd id=\"factWorldState\">Not materialized</dd></div>\n            </dl>\n          </section>\n\n          <section class=\"panel market-card-side\">\n            <div class=\"kicker\" id=\"contextKicker\">Commercial context</div>\n            <h3 id=\"contextTitle\">Night City</h3>\n            <p id=\"contextCopy\">Seller profile context appears here.</p>\n            <div class=\"market-line\" id=\"contextLine\">Read-only public preview</div>\n          </section>\n\n          <section class=\"panel\">\n            <div class=\"section-head\">\n              <h2>Known for</h2>\n              <span>Local pattern</span>\n            </div>\n            <div class=\"known-grid\" id=\"knownGrid\">\n              <span>Repair parts</span>\n              <span>Used tech</span>\n              <span>Odd electronics</span>\n              <span>Fair haggling</span>\n            </div>\n          </section>\n        </aside>\n      </div>\n\n      <div class=\"template-note\">\n        <h3>Vendor page template rules</h3>\n        <ul>\n          <li>Shop identity comes first: name, status, distance, type, owner.</li>\n          <li>Then show stock, not with modern e-commerce polish, but as a local market board.</li>\n          <li>The side column should carry state, local context, and what the seller is known for.</li>\n          <li>Desktop keeps context beside stock; mobile stacks the same blocks without changing their logic.</li>\n        </ul>\n      </div>\n\n      <footer class=\"footer\">\n        <span>Vendor record · updated 21:04</span>\n        <span>Night City / local market feed / seller supplied</span>\n      </footer>\n    </div>\n  </section>\n</div>\n\n<div class=\"stinger-layer\" id=\"stingerLayer\"></div>\n\n<script>\n/* -------- REPEATING BACK FIELD -------- */\nconst bgTrain = document.getElementById('bgTrain');\nfor(let i=-3;i<24;i++){\n  const p = document.createElement('div');\n  p.className = 'bg-period';\n  p.style.left = `${i * 204}vw`;\n  p.innerHTML = `\n    <div class=\"bg-band one\"></div>\n    <div class=\"bg-band two\"></div>\n    <div class=\"bg-band three\"></div>\n    <div class=\"bg-band four\"></div>`;\n  bgTrain.appendChild(p);\n}\nbgTrain.style.transform = `translateX(${getComputedStyle(document.documentElement).getPropertyValue('--bg-base')})`;\n\n/* -------- VIEW STATE -------- */\nconst homeView = document.getElementById('homeView');\nconst searchView = document.getElementById('searchView');\nconst vendorView = document.getElementById('vendorView');\nconst allViews = {home:homeView,search:searchView,vendor:vendorView};\nconst stingerLayer = document.getElementById('stingerLayer');\n\nlet currentView = 'home';\nlet busy = false;\nlet bgStep = 0;\n\nconst BG_BASE = -99.5;\nconst BG_PERIOD = 204;\nconst BG_DURATION = 1620;\n\nconst FG_START = 135;\nconst FG_END = -360;\nconst fgSpecs = {\n  one:   {delay:0,   duration:690},\n  two:   {delay:72,  duration:960},\n  three: {delay:150, duration:1240}\n};\n\nfunction gentleBackgroundProgress(p){\n  const join = .36;\n  if(p <= join) return p;\n\n  const s = (p - join) / (1 - join);\n  const y0 = join;\n  const y1 = 1;\n  const m0 = 1 - join;\n  const m1 = 0;\n\n  const h00 =  2*s*s*s - 3*s*s + 1;\n  const h10 =      s*s*s - 2*s*s + s;\n  const h01 = -2*s*s*s + 3*s*s;\n  const h11 =      s*s*s -   s*s;\n\n  const hermite = h00*y0 + h10*m0 + h01*y1 + h11*m1;\n  const t = Math.max(0, (s - .7) / .3);\n  const cushion = 1 - Math.pow(1 - t, 3);\n\n  return hermite + (1 - hermite) * .06 * cushion;\n}\n\nfunction createFg(which, className){\n  const el = document.createElement('div');\n  el.className = `fg-page ${className}`;\n  el.style.transform = `translateX(${FG_START}vw)`;\n  stingerLayer.appendChild(el);\n  return el;\n}\n\nfunction fgX(elapsed, spec){\n  if(elapsed <= spec.delay) return FG_START;\n  const p = Math.min(1, (elapsed - spec.delay) / spec.duration);\n  return FG_START + (FG_END - FG_START) * p;\n}\n\nfunction switchTo(target){\n  if (busy || currentView === target) return;\n  busy = true;\n\n  const panels = {\n    one: createFg('one', 'one'),\n    two: createFg('two', 'two'),\n    three: createFg('three', 'three')\n  };\n\n  const start = performance.now();\n  const bgStart = BG_BASE - (bgStep * BG_PERIOD);\n  const bgEnd = BG_BASE - ((bgStep + 1) * BG_PERIOD);\n  let swapped = false;\n\n  function frame(now){\n    const elapsed = now - start;\n\n    for (const [key, el] of Object.entries(panels)){\n      el.style.transform = `translateX(${fgX(elapsed, fgSpecs[key])}vw)`;\n    }\n\n    const bp = Math.min(1, elapsed / BG_DURATION);\n    const eased = gentleBackgroundProgress(bp);\n    const bgX = bgStart + (bgEnd - bgStart) * eased;\n    bgTrain.style.transform = `translateX(${bgX}vw)`;\n\n    const amberLead = fgX(elapsed, fgSpecs.three);\n    if (!swapped && amberLead <= -108){\n      swapped = true;\n      Object.entries(allViews).forEach(([name,view])=>view.classList.toggle('active',name===target));\n      currentView = target;\n      window.scrollTo(0,0);\n    }\n\n    const doneFG = elapsed >= fgSpecs.three.delay + fgSpecs.three.duration;\n    const doneBG = elapsed >= BG_DURATION;\n\n    if (!doneFG || !doneBG){\n      requestAnimationFrame(frame);\n      return;\n    }\n\n    bgStep++;\n    bgTrain.style.transform = `translateX(${BG_BASE - (bgStep * BG_PERIOD)}vw)`;\n\n    Object.values(panels).forEach(el => el.remove());\n    busy = false;\n  }\n\n  requestAnimationFrame(frame);\n}\n\nfunction playWipe(action){\n  if(busy)return;\n  busy=true;\n  const panels={one:createFg('one','one'),two:createFg('two','two'),three:createFg('three','three')};\n  const start=performance.now();\n  let fired=false;\n  function frame(now){\n    const elapsed=now-start;\n    for(const [key,el] of Object.entries(panels))el.style.transform=`translateX(${fgX(elapsed,fgSpecs[key])}vw)`;\n    if(!fired&&fgX(elapsed,fgSpecs.three)<=-108){\n      fired=true;\n      busy=false;\n      Promise.resolve(action()).catch(console.error);\n      window.scrollTo(0,0);\n    }\n    if(elapsed<fgSpecs.three.delay+fgSpecs.three.duration){\n      requestAnimationFrame(frame);\n      return;\n    }\n    Object.values(panels).forEach(el=>el.remove());\n    busy=false;\n  }\n  requestAnimationFrame(frame);\n}\n\n\nconst API_BASE='https://nqomqcmiecxmbiukdqhh.supabase.co/functions/v1/vendr';\nlet sellers=[];\nlet lastSearch=null;\nlet currentSellerId=null;\nlet currentFocusOffer=null;\nlet vendorHistory=[];\n\nfunction esc(v){\n  return String(v??'').replace(/[&<>'\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',\"'\":'&#39;','\"':'&quot;'}[c]));\n}\nasync function api(params){\n  const url=new URL(API_BASE);\n  Object.entries(params).forEach(([k,v])=>{if(v!==null&&v!==undefined&&v!=='')url.searchParams.set(k,String(v))});\n  const r=await fetch(url);\n  const j=await r.json().catch(()=>({}));\n  if(!r.ok)throw new Error(j.error||r.statusText);\n  return j;\n}\nfunction sellerById(id){return sellers.find(s=>s.entity_id===id)}\nfunction sellerByName(name,district=null){\n  if(!name)return null;\n  return sellers.find(s=>s.name===name&&(!district||s.district===district))||sellers.find(s=>s.name===name)||null;\n}\nfunction childSellers(s){\n  const raw=(Array.isArray(s.child_places)&&s.child_places.length)?s.child_places:(Array.isArray(s.children)?s.children:[]);\n  return raw.map(ref=>{\n    const obj=(ref&&typeof ref==='object')?ref:{};\n    const id=typeof ref==='string'?ref:(obj.child_entity_id||obj.entity_id||obj.child_id||obj.id||null);\n    const listed=id?sellerById(id):null;\n    return {\n      ...(listed||{}),\n      ...obj,\n      entity_id:id||listed?.entity_id||null,\n      name:obj.child_name||obj.name||listed?.name||id,\n      type:obj.child_type||obj.type||listed?.type||'Shop',\n      copy:obj.child_copy||obj.copy||listed?.copy||'Independent business at this location.',\n      tags:obj.child_tags||obj.tags||listed?.tags||'',\n      stock_mode:obj.child_stock_mode||obj.stock_mode||listed?.stock_mode||''\n    };\n  }).filter(x=>x.entity_id&&x.name);\n}\nfunction parentSeller(s){\n  const explicit=s.parent_id||s.parent_entity_id||s.parent?.entity_id||null;\n  if(explicit&&sellerById(explicit))return sellerById(explicit);\n  return sellerByName(s.parent_name||s.parent?.name||'',s.district);\n}\nfunction modeLabel(v){return String(v||'').replaceAll('_',' ')}\nfunction sellerRow(s,sub,status){\n  return '<button class=\"list-row\" data-shop=\"'+esc(s.entity_id)+'\"><div>'+\n    '<div class=\"row-title\">'+esc(s.name)+'</div>'+\n    '<div class=\"row-sub\">'+esc(sub||[s.type,s.district].filter(Boolean).join(' · '))+'</div></div>'+\n    '<div class=\"row-status\">'+esc(status||modeLabel(s.stock_mode))+'</div></button>';\n}\nfunction bindSellerClicks(root,offerMap=null){\n  root.querySelectorAll('[data-shop]').forEach(el=>el.addEventListener('click',()=>{\n    const id=el.dataset.shop;\n    const offers=offerMap?.get(id)||[];\n    const focus=offers.find(o=>o.kind==='available')||offers[0]||null;\n    openVendor(id,focus);\n  }));\n}\nfunction renderSellerPanel(panel,slice,subFn,statusFn,offerMap=null){\n  panel.querySelectorAll('.list-row').forEach(x=>x.remove());\n  slice.forEach(s=>panel.insertAdjacentHTML('beforeend',sellerRow(s,subFn?.(s),statusFn?.(s))));\n  if(!slice.length)panel.insertAdjacentHTML('beforeend','<div class=\"list-row\"><div><div class=\"row-title\">No matching sellers</div><div class=\"row-sub\">Try a broader search term.</div></div><div class=\"row-status amber\">None</div></div>');\n  bindSellerClicks(panel,offerMap);\n}\nfunction renderMarkets(rows){\n  const cards=document.getElementById('marketCards');\n  cards.innerHTML=rows.slice(0,3).map(s=>\n    '<article class=\"mini-card\" data-shop=\"'+esc(s.entity_id)+'\" tabindex=\"0\">'+\n    '<div class=\"mini-time\">'+esc(modeLabel(s.stock_mode))+'</div>'+\n    '<h3>'+esc(s.name)+'</h3>'+\n    '<p>'+esc(s.copy||'Canonical market or multi-vendor place in the Night City commercial graph.')+'</p>'+\n    '<div class=\"mini-dist\">'+esc(s.district||'Night City')+' · '+esc(s.type||'commercial place')+'</div></article>'\n  ).join('');\n  bindSellerClicks(cards);\n}\nfunction renderHomeDefault(){\n  const profiled=sellers.filter(s=>s.stock_profile_present||s.stock_mode!=='PLACE_ONLY');\n  const browseable=profiled.filter(s=>['DIRECT_SELLER','HYBRID_DIRECT_EVENT','EVENT_MARKET','AGGREGATE_CONTAINER'].includes(s.stock_mode));\n  const direct=profiled.filter(s=>['DIRECT_SELLER','HYBRID_DIRECT_EVENT'].includes(s.stock_mode));\n  const markets=profiled.filter(s=>['AGGREGATE_CONTAINER','EVENT_MARKET','HYBRID_DIRECT_EVENT'].includes(s.stock_mode));\n  document.getElementById('primarySellerTitle').textContent='Known sellers';\n  document.getElementById('primarySellerMeta').innerHTML='Canonical commercial<br>profiles';\n  document.getElementById('secondarySellerTitle').textContent='Direct sellers';\n  document.getElementById('secondarySellerMeta').innerHTML='Likely stocked<br>places';\n  document.getElementById('marketPanelTitle').textContent='Markets';\n  document.getElementById('marketPanelMeta').innerHTML='Containers / events<br>from the city graph';\n  renderSellerPanel(document.getElementById('primarySellerPanel'),browseable.slice(0,3),s=>[s.type,s.district].filter(Boolean).join(' · '),s=>modeLabel(s.stock_mode));\n  renderSellerPanel(document.getElementById('secondarySellerPanel'),direct.slice(0,3),s=>[s.tags,s.district].filter(Boolean).join(' · '),()=> 'SELLER');\n  renderMarkets(markets);\n}\nfunction groupSearchOffers(data){\n  const map=new Map();\n  for(const o of data.offers||[]){\n    if(!map.has(o.shop_entity_id))map.set(o.shop_entity_id,{entity_id:o.shop_entity_id,name:o.shop_name,district:o.district,stock_mode:o.stock_mode,type:'seller match',offers:[]});\n    map.get(o.shop_entity_id).offers.push(o);\n  }\n  return map;\n}\n\nfunction itemTypeLabel(o){\n  return String(o.primary_department||'item').replaceAll('-',' ');\n}\nfunction placeLabel(o){\n  const parts=[];\n  if(o.parent_name)parts.push(o.parent_name);\n  if(o.district&&!parts.includes(o.district))parts.push(o.district);\n  if(o.distance!==null&&o.distance!==undefined)parts.push(String(o.distance));\n  return parts.join(' · ')||'Night City';\n}\nfunction moneyEb(v){\n  if(v===null||v===undefined)return '—';\n  return Number(v).toLocaleString()+'eb';\n}\nfunction quantityText(row,short=false){\n  if(row?.quantity==null){\n    return row?.quantity_profile==='continuous'?(short?'ON DEMAND':'On demand'):(short?'AVAILABLE':'Available');\n  }\n  return short?String(row.quantity):(String(row.quantity)+' here');\n}\nfunction nextRefreshText(state){\n  if(!state?.next_restock_at)return state?.cadence_label||'Current stock';\n  const d=new Date(state.next_restock_at);\n  if(Number.isNaN(d.getTime()))return state?.cadence_label||'Current stock';\n  const when=new Intl.DateTimeFormat(undefined,{weekday:'short',hour:'2-digit',minute:'2-digit'}).format(d);\n  return (state?.cadence_label||'Refresh')+' · next '+when;\n}\nlet resultSortMode='location';\n\nfunction conditionRank(v){\n  const ranks={new:0,refurbished:1,used:2,salvaged:3,damaged:4,not_applicable:5};\n  return ranks[String(v||'').toLowerCase()]??9;\n}\nfunction sortOffers(rows,mode){\n  const arr=rows.slice();\n  if(mode==='price')return arr.sort((a,b)=>(a.asking_price??Infinity)-(b.asking_price??Infinity)||String(a.shop_name).localeCompare(String(b.shop_name)));\n  if(mode==='condition')return arr.sort((a,b)=>conditionRank(a.condition)-conditionRank(b.condition)||String(a.shop_name).localeCompare(String(b.shop_name)));\n  if(mode==='availability')return arr.sort((a,b)=>(b.quantity==null?999999:Number(b.quantity||0))-(a.quantity==null?999999:Number(a.quantity||0))||String(a.shop_name).localeCompare(String(b.shop_name)));\n  return arr.sort((a,b)=>String(placeLabel(a)).localeCompare(String(placeLabel(b)))||String(a.shop_name).localeCompare(String(b.shop_name)));\n}\nfunction offerRow(o,exact=false){\n  return '<button class=\"search-offer '+(exact?'exact-mode':'')+'\" data-offer-shop=\"'+esc(o.shop_entity_id)+'\" data-offer-item=\"'+esc(o.item_id)+'\">'+\n    '<div class=\"item-col\"><span class=\"item-name\">'+esc(o.item_name)+'</span>'+\n    '<span class=\"item-meta\">'+esc(itemTypeLabel(o))+' · '+esc(o.condition||'stock item')+' · '+esc(o.quantity==null?'on demand':String(o.quantity)+' available')+'</span></div>'+\n    '<div class=\"seller-col\"><span class=\"seller-name\">'+esc(o.shop_name)+'</span>'+\n    '<span class=\"place-meta\">'+esc(placeLabel(o))+'</span></div>'+\n    '<div class=\"price-block\"><span class=\"price\">'+esc(moneyEb(o.asking_price))+'</span>'+\n    '<span class=\"price-meta\">'+esc(o.condition||'')+(o.quantity!=null?' · '+esc(String(o.quantity))+' here':'')+'</span></div>'+\n  '</button>';\n}\nfunction bindOfferRows(root,data){\n  root.querySelectorAll('[data-offer-shop]').forEach(el=>el.addEventListener('click',()=>{\n    const shopId=el.dataset.offerShop;\n    const itemId=el.dataset.offerItem;\n    const offer=(data.offers||[]).find(o=>String(o.shop_entity_id)===String(shopId)&&String(o.item_id)===String(itemId))||null;\n    openVendor(shopId,offer);\n  }));\n}\nfunction renderNearbyOffers(data){\n  const available=(data.offers||[]).filter(o=>o.kind==='available');\n  const exact=Boolean(data.active_item_id);\n  const list=document.getElementById('nearbyOffersList');\n  const top=available.slice(0,4);\n  if(!top.length){\n    list.innerHTML='<div class=\"row-sub\" style=\"padding:12px 0\">No current stock reports in the selected area.</div>';\n    return;\n  }\n  list.innerHTML=top.map(o=>\n    '<button class=\"nearby-offer\" data-offer-shop=\"'+esc(o.shop_entity_id)+'\" data-offer-item=\"'+esc(o.item_id)+'\">'+\n      '<div><strong>'+esc(exact?o.shop_name:o.item_name)+'</strong>'+\n      '<span>'+esc(exact?placeLabel(o):(o.shop_name+' · '+placeLabel(o)))+'</span></div>'+\n      '<strong class=\"nearby-price\">'+esc(moneyEb(o.asking_price))+'</strong>'+\n    '</button>'\n  ).join('');\n  bindOfferRows(list,data);\n}\nfunction renderAvailableOffers(data){\n  const section=document.getElementById('availableOffersSection');\n  const list=document.getElementById('availableOffersList');\n  const available=(data.offers||[]).filter(o=>o.kind==='available');\n  const exact=Boolean(data.active_item_id);\n  document.getElementById('availableOffersMeta').textContent=available.length+' current offer'+(available.length===1?'':'s')+' · sort locally';\n  section.hidden=!available.length;\n  list.innerHTML=sortOffers(available,resultSortMode).map(o=>offerRow(o,exact)).join('');\n  bindOfferRows(list,data);\n}\nfunction renderLikelySellers(data){\n  const section=document.getElementById('plausibleOffersSection');\n  const list=document.getElementById('plausibleOffersList');\n  const exact=Boolean(data.active_item_id);\n  const plausible=(data.offers||[]).filter(o=>o.kind!=='available');\n  section.hidden=!plausible.length;\n  list.innerHTML=plausible.map(o=>\n    '<button class=\"search-offer plausible '+(exact?'exact-mode':'')+'\" data-offer-shop=\"'+esc(o.shop_entity_id)+'\" data-offer-item=\"'+esc(o.item_id)+'\">'+\n      '<div class=\"item-col\"><span class=\"item-name\">'+esc(o.item_name)+'</span>'+\n      '<span class=\"item-meta\">'+esc(itemTypeLabel(o))+' · not in current stock</span></div>'+\n      '<div class=\"seller-col\"><span class=\"seller-name\">'+esc(o.shop_name)+'</span>'+\n      '<span class=\"place-meta\">'+esc(placeLabel(o))+'</span></div>'+\n      '<div class=\"price-block\"><span class=\"price\">LIKELY SELLER</span>'+\n      '<span class=\"price-meta\">no current offer</span></div>'+\n    '</button>'\n  ).join('');\n  bindOfferRows(list,data);\n}\nfunction renderRelatedItems(data,q){\n  const section=document.getElementById('relatedItemsSection');\n  const list=document.getElementById('relatedItemsList');\n  if(!data.active_item_id){section.hidden=true;list.innerHTML='';return}\n  const active=(data.items||[]).find(x=>String(x.item_id)===String(data.active_item_id));\n  if(!active){section.hidden=true;return}\n  const related=(data.items||[]).filter(x=>String(x.item_id)!==String(active.item_id)&&x.relation_key===active.relation_key).slice(0,6);\n  section.hidden=!related.length;\n  list.innerHTML=related.map(x=>\n    '<button class=\"related-item\" type=\"button\" data-related-item=\"'+esc(x.item_id)+'\">'+\n      '<strong>'+esc(x.name)+'</strong><span>Same catalogue family →</span></button>'\n  ).join('');\n  list.querySelectorAll('[data-related-item]').forEach(el=>el.addEventListener('click',()=>runSearchPage(q,el.dataset.relatedItem)));\n}\nfunction renderOfferSections(data,q){\n  renderNearbyOffers(data);\n  renderAvailableOffers(data);\n  renderLikelySellers(data);\n  renderRelatedItems(data,q);\n}\nfunction renderSearchPage(data,q){\n  lastSearch={data,q};\n  const exact=Boolean(data.active_item_id);\n  const active=exact?(data.items||[]).find(x=>String(x.item_id)===String(data.active_item_id)):null;\n  const label=(active?.name||q||'SEARCH').toUpperCase();\n  document.getElementById('searchModeLabel').textContent=exact?'Exact catalogue item':'Broad search';\n  document.getElementById('searchQueryLine').textContent=label+' · '+(exact?'exact item':'broad catalogue search')+' · Night City-wide';\n  document.getElementById('searchMapQuery').textContent=label;\n  document.getElementById('searchPageInput').value=q;\n  document.getElementById('searchFooterLeft').textContent=exact?(active?.name||q)+' · exact item':q+' · broad search';\n  renderOfferSections(data,q);\n  document.getElementById('searchEmpty').hidden=(data.offers||[]).length>0;\n  drawSearchSpaciel(data);\n}\nfunction searchUrl(q,itemId=null){\n  const url=new URL(location.href);\n  url.search='';\n  if(q)url.searchParams.set('q',q);\n  if(itemId)url.searchParams.set('item',itemId);\n  return url.pathname+url.search;\n}\n\nasync function runSearchPage(raw,itemId=null,options={}){\n  const q=String(raw||'').trim();\n  if(!q){\n    if(options.push!==false)history.pushState({view:'home'},'',location.pathname);\n    if(currentView!=='home')switchTo('home');\n    return;\n  }\n  hideSuggestions();\n  document.getElementById('marketSearchTop').value=q;\n  document.getElementById('searchPageInput').value=q;\n  document.getElementById('searchModeLabel').textContent=itemId?'Exact catalogue item':'Broad search';\n  document.getElementById('searchQueryLine').textContent=(itemId?'LOADING ITEM…':q.toUpperCase())+' · resolving current Night City offers…';\n  document.getElementById('searchMapQuery').textContent=itemId?'ITEM':q.toUpperCase();\n  document.getElementById('availableOffersSection').hidden=true;\n  document.getElementById('plausibleOffersSection').hidden=true;\n  document.getElementById('relatedItemsSection').hidden=true;\n  document.getElementById('searchEmpty').hidden=true;\n\n  if(options.push!==false){\n    history.pushState({view:'search',q,itemId:itemId||null},'',searchUrl(q,itemId));\n  }\n\n  if(options.animate===false){\n    Object.entries(allViews).forEach(([name,view])=>view.classList.toggle('active',name==='search'));\n    currentView='search';\n    window.scrollTo(0,0);\n  }else if(currentView!=='search'){\n    switchTo('search');\n  }else{\n    window.scrollTo({top:0,behavior:'smooth'});\n  }\n\n  try{\n    const data=await api({api:'search',q,item_id:itemId||null});\n    renderSearchPage(data,q);\n  }catch(e){\n    document.getElementById('searchQueryLine').textContent='Search unavailable · '+e.message;\n    document.getElementById('searchEmpty').hidden=false;\n  }\n}\n\nlet suggestTimer=null;\nlet suggestToken=0;\nfunction hideSuggestions(){\n  const box=document.getElementById('marketSuggest');\n  box.hidden=true;\n  box.innerHTML='';\n}\nfunction renderSuggestions(data,q){\n  const box=document.getElementById('marketSuggest');\n  const items=data.items||[];\n  const total=Number(data.total_matches??items.length);\n  const needle=String(q||'').trim().toLowerCase();\n  const placeMatches=needle?sellers.filter(s=>String(s.name||'').toLowerCase().includes(needle)).slice(0,6):[];\n  if(!q){hideSuggestions();return}\n  box.innerHTML=\n    '<div class=\"suggest-head\">Places & catalogue</div>'+\n    placeMatches.map(place=>\n      '<button class=\"suggest-row\" type=\"button\" data-suggest-place=\"'+esc(place.entity_id)+'\">'+\n      '<strong>'+esc(place.name)+'</strong>'+\n      '<span>'+esc([place.type,place.district,place.stock_mode==='PLACE_ONLY'?'place profile':modeLabel(place.stock_mode)].filter(Boolean).join(' · '))+'</span></button>'\n    ).join('')+\n    items.map(item=>\n      '<button class=\"suggest-row\" type=\"button\" data-suggest-item=\"'+esc(item.item_id)+'\">'+\n      '<strong>'+esc(item.name)+'</strong>'+\n      '<span>'+esc(itemTypeLabel(item))+' · exact catalogue item</span></button>'\n    ).join('')+\n    '<button class=\"suggest-row search-all\" type=\"button\" data-search-all=\"1\">'+\n    '<strong>Search catalogue for “'+esc(q)+'”</strong>'+\n    '<span>'+esc(String(total))+' related catalogue item'+(total===1?'':'s')+' →</span></button>';\n  box.hidden=false;\n  box.querySelectorAll('[data-suggest-place]').forEach(button=>button.addEventListener('click',()=>{\n    hideSuggestions();\n    playWipe(()=>openVendor(button.dataset.suggestPlace,null,{pushHistory:true}));\n  }));\n  box.querySelectorAll('[data-suggest-item]').forEach(button=>button.addEventListener('click',()=>{\n    runSearchPage(q,button.dataset.suggestItem);\n  }));\n  box.querySelector('[data-search-all]')?.addEventListener('click',()=>runSearchPage(q,null));\n}\nfunction queueSuggestions(raw){\n  const q=String(raw||'').trim();\n  clearTimeout(suggestTimer);\n  if(q.length<2){hideSuggestions();return}\n  const token=++suggestToken;\n  suggestTimer=setTimeout(async()=>{\n    try{\n      const data=await api({api:'search',q,suggest:1});\n      if(token!==suggestToken)return;\n      renderSuggestions(data,q);\n    }catch(_){\n      if(token===suggestToken)hideSuggestions();\n    }\n  },170);\n}\nfunction renderVendorStock(s,focus){\n  const list=document.getElementById('stockList');\n  const sourceRows=Array.isArray(s.stock)?s.stock.slice():[];\n  const children=childSellers(s);\n  const stockTitle=document.getElementById('stockPanelTitle');\n  const search=document.getElementById('shopSearch');\n\n  function stockRowsHtml(rows){\n    const focusId=focus?String(focus.item_id):null;\n    const exact=focusId?rows.find(r=>String(r.item_id)===focusId):null;\n    const relation=(exact?.relation_key)||(focus?.relation_key)||null;\n    const ranked=rows.map((r,index)=>{\n      const exactHit=focusId&&String(r.item_id)===focusId;\n      const relatedHit=!exactHit&&relation&&r.relation_key===relation;\n      return {r,index,rank:exactHit?0:(relatedHit?1:2),exactHit,relatedHit};\n    }).sort((a,b)=>a.rank-b.rank||a.index-b.index);\n    return ranked.map(({r,exactHit,relatedHit})=>{\n      const rowClass=exactHit?' exact-row':(relatedHit?' related-row':'');\n      const nameClass=exactHit?' exact':(relatedHit?' related':'');\n      const flowLabel=r.last_change||null;\n      const sub=[r.assortment_role,r.condition,flowLabel,exactHit?'exact item':(relatedHit?'related item':null)].filter(Boolean).join(' · ');\n      return '<article class=\"stock-row'+rowClass+'\" data-search=\"'+esc((r.name+' '+sub).toLowerCase())+'\"><div>'+\n        '<div class=\"stock-name'+nameClass+'\">'+esc(r.name)+'</div>'+\n        '<div class=\"stock-sub\">'+esc(sub)+'</div></div>'+\n        '<div class=\"stock-meta\"><strong>'+esc(quantityText(r))+'</strong><br>'+esc((r.assortment_role||'stock')+' · state '+String(s.state?.generation??s.state?.stock_cycle??r.stock_cycle??'—'))+\n        '</div>'+\n        '<div class=\"price\">'+esc(r.asking_price==null?'—':Number(r.asking_price).toLocaleString()+'eb')+'</div></article>';\n    }).join('');\n  }\n\n  if(children.length){\n    stockTitle.textContent='Shops here';\n    search.placeholder='SEARCH SHOPS HERE';\n    const placeHtml=children.map(child=>{\n      const tags=String(child.tags||'').split('|').map(x=>x.trim()).filter(Boolean).slice(0,3);\n      const hay=[child.name,child.copy,child.type,...tags].filter(Boolean).join(' ').toLowerCase();\n      return '<button class=\"place-row\" type=\"button\" data-child-shop=\"'+esc(child.entity_id)+'\" data-search=\"'+esc(hay)+'\">'+\n        '<div><div class=\"place-name\">'+esc(child.name)+'</div>'+\n        '<div class=\"place-desc\">'+esc(child.copy||child.type||'Independent business at this location.')+'</div>'+\n        (tags.length?'<div class=\"place-tags\">'+tags.map(tag=>'<span class=\"place-tag\">'+esc(tag)+'</span>').join('')+'</div>':'')+\n        '</div><div class=\"place-meta\"><strong>'+esc(child.type||'Shop')+'</strong>'+esc(modeLabel(child.stock_mode)||'')+'</div>'+\n        '<div class=\"place-arrow\">View →</div></button>';\n    }).join('');\n    const ownStock=sourceRows.length?'<div class=\"stock-subsection-title\">Stock sold directly by '+esc(s.name||'this location')+'</div>'+stockRowsHtml(sourceRows):'';\n    list.innerHTML=placeHtml+ownStock;\n    list.querySelectorAll('[data-child-shop]').forEach(el=>el.addEventListener('click',()=>{\n      const id=el.dataset.childShop;\n      playWipe(()=>openVendor(id,null,{pushHistory:true}));\n    }));\n    document.getElementById('stockSummary').innerHTML=children.length+' place'+(children.length===1?'':'s')+' inside'+(sourceRows.length?'<br>'+sourceRows.length+' direct stock line'+(sourceRows.length===1?'':'s'):'');\n    document.getElementById('restockBand').textContent='Browse the businesses at '+(s.name||'this location');\n    return;\n  }\n\n  stockTitle.textContent='Stock';\n  search.placeholder='SEARCH THIS SHOP';\n  if(!sourceRows.length){\n    list.innerHTML='<article class=\"stock-row\" data-search=\"\"><div><div class=\"stock-name\">No shelf stock</div><div class=\"stock-sub\">This place does not currently list physical stock.</div></div><div class=\"stock-meta\"><strong>—</strong><br>no count</div><div class=\"price amber\">—</div></article>';\n    document.getElementById('stockSummary').innerHTML='No shelf stock<br>'+esc(modeLabel(s.stock_mode));\n    document.getElementById('restockBand').textContent=s.stock_mode==='SERVICE_ONLY'?'Services only':'No current shelf inventory';\n    return;\n  }\n\n  list.innerHTML=stockRowsHtml(sourceRows);\n  document.getElementById('stockSummary').innerHTML=sourceRows.length+' listed · state '+esc(String(s.state?.generation??s.state?.stock_cycle??'—'))+'<br>'+esc(s.state?.cadence_label||'Current stock');\n  document.getElementById('restockBand').textContent=nextRefreshText(s.state);\n}\nfunction renderVendor(s,offers){\n  currentSellerId=s.entity_id;\n  const children=childSellers(s);\n  const parent=parentSeller(s);\n  const parentLink=document.getElementById('parentLocationLink');\n  if(parent){\n    document.getElementById('parentLocationName').textContent=parent.name;\n    parentLink.hidden=false;\n    parentLink.dataset.parentShop=parent.entity_id;\n    parentLink.setAttribute('aria-label','Back to '+parent.name);\n  }else{\n    parentLink.hidden=true;\n    parentLink.removeAttribute('data-parent-shop');\n    parentLink.removeAttribute('aria-label');\n  }\n  const photoStrip=document.getElementById('vendorPhotoStrip');\n  const photoCredit=document.getElementById('vendorPhotoCredit');\n  if(s.image&&s.image.image_url){\n    const fx=Math.max(0,Math.min(1,Number(s.image.focal_x??0.5)))*100;\n    const fy=Math.max(0,Math.min(1,Number(s.image.focal_y??0.5)))*100;\n    photoStrip.style.backgroundImage='linear-gradient(90deg,rgba(23,17,12,.48) 0%,rgba(23,17,12,.22) 46%,rgba(23,17,12,.04) 100%), url(\"'+String(s.image.image_url).replace(/\"/g,'%22')+'\")';\n    photoStrip.style.backgroundPosition=fx+'% '+fy+'%';\n    photoCredit.innerHTML='PHOTO · <a href=\"'+esc(s.image.source_url)+'\" target=\"_blank\" rel=\"noopener\">'+esc(s.image.photographer)+'</a> / <a href=\"'+esc(s.image.attribution_url)+'\" target=\"_blank\" rel=\"noopener\">UNSPLASH</a>';\n  }else{\n    photoStrip.style.backgroundImage='linear-gradient(135deg,#3c3329,#17110c)';\n    photoStrip.style.backgroundPosition='50% 50%';\n    photoCredit.textContent='';\n  }\n  document.getElementById('vendorName').textContent=s.name||'Seller';\n  document.getElementById('vendorKicker').textContent=parent?((parent.name||'Containing location')+' / '+(s.type||'vendor')):'Night City / '+(s.type||'seller profile');\n  document.getElementById('vendorStatus').textContent=children.length?(children.length+' SHOP'+(children.length===1?'':'S')+' HERE'):((s.stock||[]).length?'STOCK · CYCLE 1':'PROFILE · READ ONLY');\n  document.getElementById('vendorDistrict').textContent=s.district||'Night City';\n  document.getElementById('vendorType').textContent=s.type||'Commercial place';\n  document.getElementById('vendorStockMode').textContent=modeLabel(s.stock_mode);\n  document.getElementById('vendorCopy').textContent=s.blurb||s.copy||s.short_description||s.modelling_note||'';\n  if(s.owner&&s.owner.name){\n    document.getElementById('vendorOwnerLabel').textContent=s.owner.name;\n    document.getElementById('vendorOwnerSub').textContent=[s.owner.role,s.owner.note].filter(Boolean).join(' · ');\n  }else{\n    document.getElementById('vendorOwnerLabel').textContent=parent?'Located in':'Vend-R listing';\n    document.getElementById('vendorOwnerSub').textContent=parent?parent.name:(s.source_ref||'Night City 2045');\n  }\n  document.getElementById('restockBand').textContent='Loading stock snapshot…';\n  document.getElementById('factStatus').textContent='Profile only';\n  document.getElementById('factDistrict').textContent=s.district||'Night City';\n  document.getElementById('factStockMode').textContent=modeLabel(s.stock_mode);\n  document.getElementById('factArchetype').textContent=s.type||'—';\n  document.getElementById('factSource').textContent=s.source_ref||'Night City 2045';\n  document.getElementById('factWorldState').textContent='Not materialized';\n  if(children.length){\n    document.getElementById('contextKicker').textContent='At this location';\n    document.getElementById('contextTitle').textContent=children.length+' shop'+(children.length===1?'':'s')+' here';\n    document.getElementById('contextCopy').textContent='Each business below has its own profile, details and stock.';\n    document.getElementById('contextLine').textContent=(s.district||'Night City')+' · browse inside';\n  }else if(parent){\n    document.getElementById('contextKicker').textContent='Inside';\n    document.getElementById('contextTitle').textContent=parent.name;\n    document.getElementById('contextCopy').textContent=parent.copy||('Part of '+parent.name+'.');\n    document.getElementById('contextLine').textContent='View containing location';\n  }else{\n    document.getElementById('contextKicker').textContent='Commercial context';\n    document.getElementById('contextTitle').textContent=s.district||'Night City';\n    document.getElementById('contextCopy').textContent=s.other||s.short_description||s.copy||s.modelling_note||'';\n    document.getElementById('contextLine').textContent=modeLabel(s.stock_mode)+' · '+(s.type||'seller');\n  }\n  const display=s.display_tags||{};\n  const known=[...new Set([\n    s.shop_scale?('SIZE · '+String(s.shop_scale).toUpperCase()):null,\n    ...(display.known_for||[]),\n    ...(display.trade||[]),\n    ...String(s.tags||'').split('|').map(x=>x.trim()).filter(Boolean)\n  ].filter(Boolean))].slice(0,6);\n  document.getElementById('knownGrid').innerHTML=(known.length?known:[s.type].filter(Boolean)).map(x=>'<span>'+esc(x)+'</span>').join('');\n  const focus=offers||null;\n  currentFocusOffer=focus;\n  const exact=focus?(s.stock||[]).find(r=>String(r.item_id)===String(focus.item_id)):null;\n  const offer=document.getElementById('offerFocus');\n  if(focus){\n    offer.hidden=false;\n    document.getElementById('offerItemName').textContent=focus.item_name||exact?.name||'Selected item';\n    if(exact){\n      document.getElementById('offerKicker').textContent='Current offer';\n      document.getElementById('offerPrice').textContent=exact.asking_price==null?'—':Number(exact.asking_price).toLocaleString()+'eb';\n      document.getElementById('offerQuantity').textContent=(exact.quantity==null?'On demand':String(exact.quantity)+' available')+' · '+(exact.condition||'stock item');\n      document.getElementById('offerSub').textContent='This is the item that brought you to '+(s.name||'this seller')+'.';\n    }else{\n      document.getElementById('offerKicker').textContent='You were looking for';\n      document.getElementById('offerPrice').textContent='NO CURRENT OFFER';\n      document.getElementById('offerQuantity').textContent='related stock shown first';\n      document.getElementById('offerSub').textContent=(s.name||'This seller')+' is a plausible seller for this catalogue item, but its current resolved stock does not contain it.';\n    }\n  }else{\n    offer.hidden=true;\n  }\n  document.getElementById('factStatus').textContent=(s.stock||[]).length?'Stock state '+String(s.state?.generation??s.state?.stock_cycle??'—'):'Profile only';\n  document.getElementById('factWorldState').textContent=(s.stock||[]).length?nextRefreshText(s.state):'No shelf inventory';\n  renderVendorStock(s,focus);\n  filterShopStock('');\n}\nasync function openVendor(id,focus=null,options={}){\n  if(busy)return;\n  const pushHistory=options.pushHistory!==false;\n  const previous=currentView==='vendor'&&currentSellerId?currentSellerId:currentView;\n  try{\n    const s=await api({api:'shop',id});\n    if(pushHistory&&previous!==id)vendorHistory.push(previous);\n    renderVendor(s,focus);\n    switchTo('vendor');\n  }catch(e){\n    console.error(e);\n  }\n}\nfunction goBackFromVendor(){\n  const previous=vendorHistory.pop()||'home';\n  if(previous==='home'||previous==='search'){\n    currentSellerId=null;\n    switchTo(previous);\n    return;\n  }\n  openVendor(previous,null,{pushHistory:false});\n}\nfunction filterShopStock(q){\n  q=String(q||'').trim().toLowerCase();\n  document.querySelectorAll('#stockList .stock-row, #stockList .place-row').forEach(row=>{\n    const hay=(row.textContent+' '+(row.dataset.search||'')).toLowerCase();\n    row.style.display=(!q||hay.includes(q))?'':'none';\n  });\n}\n\nfunction hash01(value,salt=0){\n  let h=2166136261 ^ salt;\n  const s=String(value||'');\n  for(let i=0;i<s.length;i++){\n    h^=s.charCodeAt(i);\n    h=Math.imul(h,16777619);\n  }\n  return ((h>>>0)%10000)/10000;\n}\nfunction paintSpaciel(canvas,readoutId,signalRows){\n  if(!canvas)return;\n  const rect=canvas.getBoundingClientRect();\n  if(rect.width<2||rect.height<2)return;\n  const dpr=Math.min(window.devicePixelRatio||1,2);\n  canvas.width=Math.round(rect.width*dpr);\n  canvas.height=Math.round(rect.height*dpr);\n  const ctx=canvas.getContext('2d');\n  ctx.setTransform(dpr,0,0,dpr,0,0);\n  const w=rect.width,h=rect.height;\n  ctx.clearRect(0,0,w,h);\n  const roadSets=[\n    [[.02,.77],[.18,.69],[.33,.63],[.49,.54],[.68,.49],[.97,.34]],\n    [[.00,.33],[.17,.39],[.30,.43],[.46,.46],[.61,.55],[.79,.69],[1,.78]],\n    [[.13,.02],[.20,.21],[.27,.36],[.33,.56],[.40,.74],[.49,.99]],\n    [[.65,.00],[.61,.18],[.58,.35],[.59,.51],[.68,.68],[.82,.89]],\n    [[.00,.58],[.22,.55],[.40,.56],[.59,.62],[.80,.60],[1,.51]],\n    [[.33,.00],[.36,.19],[.44,.34],[.58,.44],[.78,.46],[1,.43]],\n    [[.04,.91],[.23,.82],[.41,.78],[.57,.75],[.73,.78],[.94,.95]]\n  ];\n  ctx.lineCap='round';\n  roadSets.forEach((road,idx)=>{\n    ctx.beginPath();\n    road.forEach((p,i)=>{const x=p[0]*w,y=p[1]*h;if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y)});\n    ctx.strokeStyle=idx===0?'rgba(244,210,70,.72)':'rgba(202,221,216,.24)';\n    ctx.lineWidth=idx===0?2.2:1.15;ctx.stroke();\n  });\n  for(let i=0;i<18;i++){\n    const y=(.07+i*.051)*h,wobble=(i%3)*.012*w;\n    ctx.beginPath();ctx.moveTo(-.02*w,y);ctx.lineTo(.22*w+wobble,y-.035*h);ctx.lineTo(.48*w-wobble,y+.012*h);ctx.lineTo(.72*w+wobble,y-.02*h);ctx.lineTo(1.02*w,y+.018*h);\n    ctx.strokeStyle='rgba(130,164,160,.08)';ctx.lineWidth=.7;ctx.stroke();\n  }\n  const live=(signalRows||[]).slice(0,18);\n  live.forEach((s,i)=>{\n    const key=s.shop_entity_id||s.entity_id||s.shop_name||i;\n    const x=(.12+hash01(key,31)*.76)*w,y=(.16+hash01(key,79)*.68)*h;\n    ctx.beginPath();ctx.arc(x,y,3.3,0,Math.PI*2);ctx.fillStyle=i<4?'#f4d246':'#fff6df';ctx.fill();\n    ctx.beginPath();ctx.arc(x,y,i<4?7:5.7,0,Math.PI*2);ctx.strokeStyle=i<4?'rgba(244,210,70,.38)':'rgba(255,246,223,.22)';ctx.lineWidth=1;ctx.stroke();\n  });\n  ctx.strokeStyle='rgba(240,91,19,.74)';ctx.lineWidth=1.2;ctx.strokeRect(w*.44,h*.42,w*.12,h*.12);\n  ctx.beginPath();ctx.moveTo(w*.50,h*.39);ctx.lineTo(w*.50,h*.57);ctx.moveTo(w*.41,h*.48);ctx.lineTo(w*.59,h*.48);ctx.stroke();\n  const readout=document.getElementById(readoutId);\n  if(readout)readout.textContent=live.length+' VEND-R SIGNAL'+(live.length===1?'':'S')+' · NIGHT CITY';\n}\nfunction drawSpaciel(){\n  const live=sellers.filter(s=>['DIRECT_SELLER','HYBRID_DIRECT_EVENT','EVENT_MARKET'].includes(s.stock_mode));\n  paintSpaciel(document.getElementById('spacielCanvas'),'spacielReadout',live);\n}\nfunction drawSearchSpaciel(data=lastSearch?.data){\n  const live=(data?.offers||[]).filter(o=>o.kind==='available');\n  paintSpaciel(document.getElementById('searchSpacielCanvas'),'searchSpacielReadout',live);\n}\nwindow.addEventListener('resize',()=>{drawSpaciel();drawSearchSpaciel()});\n\ndocument.getElementById('resultsSort').addEventListener('click',e=>{\n  const button=e.target.closest('[data-sort]');\n  if(!button||!lastSearch)return;\n  resultSortMode=button.dataset.sort;\n  document.querySelectorAll('#resultsSort [data-sort]').forEach(x=>x.classList.toggle('on',x===button));\n  renderAvailableOffers(lastSearch.data);\n});\n\nasync function boot(){\n  try{\n    const [h,s]=await Promise.all([api({api:'health'}),api({api:'shops'})]);\n    sellers=s.shops||[];\n    document.getElementById('marketPulse').textContent=(h.profiles||sellers.length)+' seller profiles · '+(h.places||650)+' mapped places · '+(h.catalog_items||1275)+' catalogue items';\n    renderHomeDefault();\n    drawSpaciel();\n\n    const params=new URLSearchParams(location.search);\n    const q=params.get('q');\n    const item=params.get('item');\n    if(q){\n      await runSearchPage(q,item,{push:false,animate:false});\n    }else{\n      history.replaceState({view:'home'},'',location.pathname);\n    }\n  }catch(e){\n    document.getElementById('marketPulse').textContent='Market data unavailable';\n  }\n}\n\nconst marketInput=document.getElementById('marketSearchTop');\nmarketInput.addEventListener('input',e=>queueSuggestions(e.currentTarget.value));\nmarketInput.addEventListener('keydown',e=>{\n  if(e.key==='Enter'){\n    e.preventDefault();\n    runSearchPage(e.currentTarget.value,null);\n  }else if(e.key==='Escape'){\n    hideSuggestions();\n  }\n});\nmarketInput.addEventListener('focus',e=>{if(String(e.currentTarget.value||'').trim().length>=2)queueSuggestions(e.currentTarget.value)});\ndocument.addEventListener('click',e=>{\n  const searchLabel=marketInput.closest('.inline-search');\n  if(searchLabel&&!searchLabel.contains(e.target))hideSuggestions();\n});\n\ndocument.getElementById('marketBrowseButton').addEventListener('click',()=>{\n  hideSuggestions();\n  window.scrollTo({top:document.querySelector('#homeView .grid-2').offsetTop-20,behavior:'smooth'});\n});\ndocument.getElementById('searchPageForm').addEventListener('submit',e=>{\n  e.preventDefault();\n  runSearchPage(document.getElementById('searchPageInput').value,null);\n});\ndocument.getElementById('searchBackHome').addEventListener('click',()=>{\n  history.pushState({view:'home'},'',location.pathname);\n  switchTo('home');\n});\ndocument.getElementById('backToMarket').addEventListener('click',goBackFromVendor);\ndocument.getElementById('parentLocationLink').addEventListener('click',e=>{\n  const id=e.currentTarget.dataset.parentShop;\n  if(id)playWipe(()=>openVendor(id,null,{pushHistory:false}));\n});\ndocument.getElementById('shopSearch').addEventListener('input',e=>filterShopStock(e.currentTarget.value));\n\nwindow.addEventListener('popstate',()=>{\n  const params=new URLSearchParams(location.search);\n  const q=params.get('q');\n  const item=params.get('item');\n  if(q){\n    runSearchPage(q,item,{push:false});\n  }else if(currentView!=='home'){\n    switchTo('home');\n  }\n});\n\nboot();\n</script>\n</body>\n</html>";

Deno.serve(async(req:Request)=>{
  if(req.method==='OPTIONS') return new Response('ok',{headers:JH});
  try{
    const u=new URL(req.url), a=u.searchParams.get('api');
    if(a==='health') return await health();
    if(a==='stock_audit') return await stockAudit();
    if(a==='shops') return await shops();
    if(a==='search') return await search(u);
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
    return new Response(HTML,{headers:{'content-type':'text/html; charset=utf-8'}});
  }catch(e){return out({error:e instanceof Error?e.message:String(e)},500)}
});