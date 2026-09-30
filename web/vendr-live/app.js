(() => {
  const $ = id => document.getElementById(id);
  const state = {gm:false,source:'all',shops:[],district:'ALL',currentShop:null,currentShopData:null,currentItem:null,eventId:'rc-demo-night-01',searchData:null,searchQuery:'',searchItem:null};
  const views={home:$('homeView'),shop:$('shopView'),search:$('searchView'),item:$('itemView')};
  function toast(message,error=false){const el=$('toast');el.textContent=message;el.classList.toggle('error',error);el.classList.add('show');clearTimeout(window.__vendrToast);window.__vendrToast=setTimeout(()=>el.classList.remove('show'),2800)}
  function go(name){Object.values(views).forEach(v=>v.classList.remove('active'));views[name].classList.add('active');window.scrollTo({top:0,behavior:'smooth'})}
  function playWipe(callback){
    const wipe=$('pageWipe');
    if(!wipe){callback();return}
    wipe.classList.remove('play');
    void wipe.offsetWidth;
    wipe.classList.add('play');
    window.setTimeout(callback,170);
    window.setTimeout(()=>wipe.classList.remove('play'),620);
  }
  function enc(v){return encodeURIComponent(v)}
  function sourceQuery(){return state.source==='all'?'':`sources=${enc(state.source)}`}
  function eventQuery(shop){return shop?.event_id?`event_id=${enc(shop.event_id)}`:''}
  function queryString(parts){const p=parts.filter(Boolean);return p.length?'?'+p.join('&'):''}
  async function api(path,options={}){const response=await fetch(path,{headers:{'Content-Type':'application/json'},...options});let body={};try{body=await response.json()}catch(e){}if(!response.ok)throw new Error(body.error||`${response.status} ${response.statusText}`);return body}
  function money(v){if(v===null||v===undefined)return '—';return `€$${Number(v).toLocaleString(undefined,{maximumFractionDigits:2})}`}
  function qty(v){return v===null||v===undefined?'∞':String(v)}
  function esc(s){return String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
  function shopById(id){return state.shops.find(s=>s.entity_id===id)}
  async function health(){try{const h=await api('/api/health');$('healthText').textContent=`CONNECTED · ${h.catalog_items.toLocaleString()} CATALOGUE ITEMS`;}catch(e){$('healthText').textContent='BACKEND OFFLINE';$('healthText').classList.add('error');toast('Vend-R API is offline. Start scripts/vendr_demo_server.py.',true)}}
  async function loadShops(){const data=await api('/api/shops');state.shops=data.shops||[];renderDistricts();renderShops()}
  function renderDistricts(){const ds=['ALL',...new Set(state.shops.map(s=>s.district).filter(Boolean))];$('districtFilters').innerHTML=ds.map(d=>`<button class="${state.district===d?'on':''}" data-district="${esc(d)}">${esc(d)}</button>`).join('');$('districtFilters').querySelectorAll('button').forEach(b=>b.addEventListener('click',()=>{state.district=b.dataset.district;renderDistricts();renderShops()}))}
  function renderShops(){const rows=state.shops.filter(s=>state.district==='ALL'||s.district===state.district);$('shopGrid').innerHTML=rows.map(s=>`<button class="shop-card" data-shop="${esc(s.entity_id)}"><span class="district">${esc(s.district||'CITYWIDE')}</span><h3>${esc(s.name)}</h3><p>${esc(s.copy||s.type||'')}</p><div class="status"><span>${esc(s.stock_mode.replaceAll('_',' '))}</span><span class="${s.materialized?'materialized':''}">${s.materialized?'WORLD STATE SAVED':'UNOPENED'}</span></div></button>`).join('');$('shopGrid').querySelectorAll('[data-shop]').forEach(b=>b.addEventListener('click',()=>openShop(b.dataset.shop)))}
  async function openShop(id){state.currentShop=id;state.currentItem=null;go('shop');$('shopFrame').hidden=true;$('shopLoading').hidden=false;$('shopLoading').textContent='Opening shop state…';try{const listed=shopById(id);const q=queryString([sourceQuery(),eventQuery(listed)]);const data=await api(`/api/shops/${enc(id)}${q}`);state.currentShopData=data;renderShop(data);$('shopFrame').hidden=false;$('shopLoading').hidden=true;await loadShops()}catch(e){$('shopLoading').textContent=`Could not open shop: ${e.message}`;$('shopLoading').classList.add('error')}}
  function renderShop(s){$('crumbDistrict').textContent=s.district||'CITYWIDE';$('crumbShop').textContent=s.name;$('shopType').textContent=s.type||s.stock_mode;$('shopMode').textContent=s.stock_mode.replaceAll('_',' ');$('shopName').textContent=s.name.toUpperCase();$('shopDistrict').textContent=s.district||'Citywide';$('shopParent').textContent=s.parent_name?`INSIDE ${s.parent_name}`:'';$('shopTags').textContent=s.tags||'';$('shopCopy').textContent=s.copy||'';$('sourceRef').textContent=s.source_ref||'Vend-R world state';$('knowTitle').textContent=s.stock_mode==='EVENT_MARKET'?'Known host / event inventory':s.stock_mode==='AGGREGATE_CONTAINER'?'Known multi-vendor place':'Known canonical seller';$('knowCopy').textContent=s.modelling_note||'The place identity is canonical; current stock is Vend-R world state.';$('persistState').textContent=s.materialized?'MATERIALIZED':'NO INVENTORY OBJECT';$('persistText').textContent=s.materialized?'This shop now has a durable Catalogger assortment and stock bundle. Reloading the page reads the same state.':(s.stock_mode==='AGGREGATE_CONTAINER'?'This parent place deliberately owns no inventory.':'Opening a stock-owning seller will create its first persistent bundle.');const contract=s.source_contract===null||s.source_contract===undefined?'all catalogue sources':s.source_contract.join(', ');$('sourceContract').textContent=s.materialized?`Persistent source contract: ${contract}.`:`If opened now: ${state.source==='all'?'all catalogue sources':state.source}.`;renderStock(s);renderGM(s)}
  function renderStock(s){const rows=s.stock||[];$('stockRows').innerHTML='';$('noStock').hidden=true;if(!rows.length){$('noStock').hidden=false;if(s.stock_mode==='AGGREGATE_CONTAINER'){const children=(s.children||[]).map(id=>shopById(id)).filter(Boolean);$('noStock').innerHTML=`<b>No parent inventory.</b><p>This place delegates stock to its child businesses.</p>${children.map(c=>`<button class="child-button" data-child="${esc(c.entity_id)}"><b>${esc(c.name)}</b><br><small>${esc(c.type||'')}</small></button>`).join('')}`;$('noStock').querySelectorAll('[data-child]').forEach(b=>b.addEventListener('click',()=>openShop(b.dataset.child)))}else if(s.stock_mode==='SERVICE_ONLY')$('noStock').textContent='This is service-led and has no static shelf inventory.';else $('noStock').textContent='No current stock rows.';return}$('stockRows').innerHTML=rows.map(r=>{const buyable=r.status==='in_stock'&&r.quantity!==null&&Number(r.quantity)>0&&r.visibility==='public';const klass=r.status==='sold'?'sold':(r.status==='incoming'?'incoming':'');return `<div class="stock-row ${klass}"><button class="item-button" data-item="${esc(r.item_id)}"><span>${esc(r.name)}</span><small>${esc([r.assortment_role,r.condition,r.visibility].filter(Boolean).join(' · '))}</small></button><span class="qty">${r.status==='incoming'?'→ ':''}${qty(r.quantity)}</span><span class="price">${money(r.asking_price)}</span><button class="buy" data-buy="${esc(r.item_id)}" ${buyable?'':'disabled'}>${r.status==='sold'?'SOLD':r.status==='incoming'?'INCOMING':r.visibility!=='public'?'ASK':'TAKE'}</button></div>`}).join('');$('stockRows').querySelectorAll('[data-item]').forEach(b=>b.addEventListener('click',()=>openItem(b.dataset.item)));$('stockRows').querySelectorAll('[data-buy]').forEach(b=>b.addEventListener('click',e=>{e.stopPropagation();purchase(b.dataset.buy)}))}
  function renderGM(s){$('gmEntity').textContent=s.entity_id;$('gmCycle').textContent=s.state?`STOCK CYCLE ${s.state.stock_cycle}`:'NO STOCK CYCLE';$('gmAssortment').textContent=s.state?`${s.state.assortment_count} persistent lines`:'—';$('gmHistory').textContent=s.state?`${s.state.history_count} events`:'—';const conditions=s.state?.temporary_conditions||[];$('gmConditions').textContent=conditions.length?conditions.map(x=>x.type).join(', '):'none';$('restockButton').disabled=!s.materialized||s.stock_mode==='EVENT_MARKET';$('conditionButton').disabled=!s.materialized;$('clearConditionsButton').disabled=!s.materialized||!conditions.length;$('eventList').innerHTML=(s.events||[]).slice().reverse().map(e=>`<div class="event"><b>${esc(e.event_type)}</b>${e.item_name?` · ${esc(e.item_name)}`:''}${e.quantity_delta!==null&&e.quantity_delta!==undefined?` · ${e.quantity_delta>0?'+':''}${e.quantity_delta}`:''}</div>`).join('')||'<div class="event">No recorded events yet.</div>'}
  function openItem(itemId){const s=state.currentShopData;if(!s)return;const r=(s.stock||[]).find(x=>x.item_id===itemId);if(!r)return;state.currentItem=r;$('itemName').textContent=r.name;$('itemSeller').textContent=s.name;$('itemQuantity').textContent=qty(r.quantity);$('itemPrice').textContent=money(r.asking_price);$('itemCondition').textContent=r.condition||'—';$('itemSources').textContent=r.source_codes?.length?`Catalogue sources: ${r.source_codes.join(', ')}`:'Catalogue source reference available through Catalogger.';const buyable=r.status==='in_stock'&&r.quantity!==null&&Number(r.quantity)>0&&r.visibility==='public';$('itemBuy').disabled=!buyable;$('itemBuy').textContent=buyable?'TAKE ONE':r.status==='sold'?'SOLD OUT':'NOT DIRECTLY AVAILABLE';go('item')}
  async function purchase(itemId){const s=state.currentShopData;if(!s)return;try{const data=await api(`/api/shops/${enc(s.entity_id)}/purchase`,{method:'POST',body:JSON.stringify({item_id:itemId,quantity:1,event_id:s.event_id})});state.currentShopData=data;renderShop(data);toast('Purchase stored. Reloading will keep this change.')}catch(e){toast(e.message,true)}}
  async function restock(){const s=state.currentShopData;if(!s)return;try{const data=await api(`/api/shops/${enc(s.entity_id)}/restock`,{method:'POST',body:JSON.stringify({event_id:s.event_id})});state.currentShopData=data;renderShop(data);toast(`Advanced to stock cycle ${data.state.stock_cycle}.`)}catch(e){toast(e.message,true)}}
  async function addCondition(){const s=state.currentShopData;if(!s)return;const type=$('conditionType').value;try{const data=await api(`/api/shops/${enc(s.entity_id)}/conditions`,{method:'POST',body:JSON.stringify({type,event_id:s.event_id})});state.currentShopData=data;renderShop(data);toast(`${type.replaceAll('_',' ')} added; it will bend the next restock cycle.`)}catch(e){toast(e.message,true)}}
  async function clearConditions(){const s=state.currentShopData;if(!s)return;try{const data=await api(`/api/shops/${enc(s.entity_id)}/clear-conditions`,{method:'POST',body:JSON.stringify({event_id:s.event_id})});state.currentShopData=data;renderShop(data);toast('Temporary stock conditions cleared.')}catch(e){toast(e.message,true)}}
  function renderSearch(data){
    state.searchData=data;
    state.searchQuery=data.query||'';
    state.searchItem=data.active_item_id||null;
    const items=data.items||[];
    const active=state.searchItem?items.find(x=>String(x.item_id)===String(state.searchItem)):null;
    const offers=data.offers||[];
    const shops=state.searchItem?[]:(data.shop_name_matches||[]);

    $('searchPageTitle').textContent=(active?.name||state.searchQuery||'SEARCH').toUpperCase();
    $('searchInput2').value=state.searchQuery;

    $('exactItemTabs').innerHTML=items.map(item=>`<button class="exact-item-tab ${String(item.item_id)===String(state.searchItem)?'selected':''}" data-exact-item="${esc(item.item_id)}">${esc(item.name)}</button>`).join('');
    $('exactItemTabs').querySelectorAll('[data-exact-item]').forEach(button=>{
      button.addEventListener('click',()=>{
        const id=button.dataset.exactItem;
        const next=String(state.searchItem)===String(id)?null:id;
        playWipe(()=>runSearch(state.searchQuery,next));
      });
    });

    if(active){
      $('exactItemNote').textContent=`${active.name} selected. Tap it again to return to the broader “${state.searchQuery}” search.`;
      $('searchModeLabel').textContent='Exact catalogue item';
      $('searchResultsTitle').textContent='WHO HAS IT';
      $('searchContextTitle').textContent=active.name;
      $('searchContextCopy').textContent=`Vend-R is showing seller results only for the exact catalogue object “${active.name}”. The other buttons remain available because their names also contain “${state.searchQuery}”.`;
    }else{
      $('exactItemNote').textContent=items.length
        ? `${items.length} exact catalogue item name${items.length===1?'':'s'} contain “${state.searchQuery}”. Select one to narrow the city; leave all unselected for the broad search.`
        : `No exact catalogue item names contain “${state.searchQuery}”.`;
      $('searchModeLabel').textContent='Broad search';
      $('searchResultsTitle').textContent='AVAILABLE AROUND NIGHT CITY';
      $('searchContextTitle').textContent=`${state.searchQuery||'Vend-R'} search`;
      $('searchContextCopy').textContent=`This is the broad search state for “${state.searchQuery}”: Vend-R can mix different matching catalogue items and existing sellers. Nothing in the item strip is selected.`;
    }

    $('searchSummary').textContent=`${offers.length} seller result${offers.length===1?'':'s'} · ${items.length} exact catalogue match${items.length===1?'':'es'}`;

    const offerRows=offers.map(r=>`<button class="result-row ${r.kind}" data-result-shop="${esc(r.shop_entity_id)}">
      <div class="result-object"><b>${esc(r.item_name)}</b><span>${esc(r.kind==='available'?'available now':'plausible stock')}</span></div>
      <div class="result-place"><b>${esc(r.shop_name)}</b><span>${esc(r.district||'Night City')}</span></div>
      <div class="result-state">${r.kind==='available'
        ? `<b>${r.quantity===null?'stocked':`qty ${qty(r.quantity)}`}</b><span>${money(r.asking_price)}</span>`
        : `<b>FIT ${r.score??'—'}</b><span>unopened</span>`
      }</div>
    </button>`);

    const shopRows=shops.map(s=>`<button class="result-row shop-match" data-result-shop="${esc(s.entity_id)}">
      <div class="result-object"><b>Place name match</b><span>canonical place</span></div>
      <div class="result-place"><b>${esc(s.name)}</b><span>${esc(s.district||'Night City')}</span></div>
      <div class="result-state"><b>PLACE</b><span>open profile</span></div>
    </button>`);

    const rows=[...offerRows,...shopRows];
    $('searchResults').innerHTML=rows.length?rows.join(''):'<div class="empty-state search-empty">No existing seller matched this search state.</div>';
    $('searchResults').querySelectorAll('[data-result-shop]').forEach(button=>button.addEventListener('click',()=>playWipe(()=>openShop(button.dataset.resultShop))));
  }

  async function runSearch(q,itemId=null){
    q=q.trim();
    if(!q)return;
    state.searchQuery=q;
    state.searchItem=itemId;
    go('search');
    $('searchInput2').value=q;
    $('searchPageTitle').textContent=(itemId?'LOADING ITEM…':q.toUpperCase());
    $('searchSummary').textContent='Searching catalogue and current world…';
    $('searchResults').innerHTML='<div class="loading">Resolving sellers without materializing unopened stock…</div>';
    try{
      const data=await api(`/api/search${queryString([
        `q=${enc(q)}`,
        sourceQuery(),
        `event_id=${enc(state.eventId)}`,
        itemId?`item_id=${enc(itemId)}`:''
      ])}`);
      renderSearch(data);
    }catch(e){
      $('searchSummary').textContent=e.message;
      $('searchSummary').classList.add('error');
      $('searchResults').innerHTML='';
    }
  }

  function toggleGM(){state.gm=!state.gm;$('app').classList.toggle('gm-on',state.gm);$('gmButton').classList.toggle('on',state.gm);$('gmButton').textContent=state.gm?'GM ON':'GM';$('worldLabel').textContent=state.gm?'NIGHT CITY 2045 · GM OVERLAY':'NIGHT CITY 2045 · LIVE SLICE'}
  function setSource(value){state.source=value;$('sourceButton').textContent=value==='all'?'SOURCES · ALL':'SOURCES · CORE';$('sourcePopover').hidden=true;toast(value==='all'?'New shops may use all catalogue sources.':'Unopened shops will be materialized using CP:R only.')}
  async function reset(){if(!confirm('Clear all materialized shop state for this demo slice?'))return;try{const r=await api('/api/reset',{method:'POST',body:'{}'});state.currentShopData=null;await loadShops();go('home');toast(`Cleared ${r.deleted_state_files} saved shop bundle(s).`)}catch(e){toast(e.message,true)}}
  document.querySelectorAll('[data-go="home"]').forEach(b=>b.addEventListener('click',()=>go('home')));$('gmButton').addEventListener('click',toggleGM);$('sourceButton').addEventListener('click',()=>{$('sourcePopover').hidden=!$('sourcePopover').hidden});$('sourcePopover').querySelectorAll('[data-source]').forEach(b=>b.addEventListener('click',()=>setSource(b.dataset.source)));$('heroSearch').addEventListener('submit',e=>{e.preventDefault();runSearch($('searchInput').value)});$('searchForm').addEventListener('submit',e=>{e.preventDefault();runSearch($('searchInput2').value)});$('itemBack').addEventListener('click',()=>go('shop'));$('itemBuy').addEventListener('click',()=>state.currentItem&&purchase(state.currentItem.item_id).then(()=>{if(state.currentShopData){const updated=state.currentShopData.stock.find(x=>x.item_id===state.currentItem.item_id);if(updated){state.currentItem=updated;openItem(updated.item_id)}}}));$('restockButton').addEventListener('click',restock);$('conditionButton').addEventListener('click',addCondition);$('clearConditionsButton').addEventListener('click',clearConditions);$('resetButton').addEventListener('click',reset);document.addEventListener('click',e=>{if(!$('sourcePopover').hidden&&!$('sourcePopover').contains(e.target)&&e.target!==$('sourceButton'))$('sourcePopover').hidden=true});Promise.all([health(),loadShops()]).catch(e=>toast(e.message,true));
})();
