const $ = (id) => document.getElementById(id);
const money = (value) => value == null ? '—' : Number(value).toLocaleString('pt-BR', {style:'currency', currency:'BRL'});
const numeric = (value, digits=5) => value == null ? '—' : Number(value).toLocaleString('pt-BR', {maximumFractionDigits:digits});
const initials = (name) => name.split(/\s+/).map(p=>p[0]).slice(0,2).join('').toUpperCase();
const monthName = (ref) => new Date(`${ref}-15T12:00:00`).toLocaleDateString('pt-BR',{month:'short',year:'numeric'}).replace(' de ', '/');
let state = {clients:[], profiles:{}, labels:{}, client:null, invoice:null, reference:'', dirty:false, calculation:null, payment:null, version:0};
let navigation = 0, calculationSequence = 0, timer, previewUrl, editorId=null, saving=false;
let requestController;
const drafts = new Map();
const draftKey = () => `${state.client?.id}:${state.reference}`;

function notice(id, message) { $(id).textContent=message || ''; $(id).hidden=!message; }
function toast(message) { $('toast').textContent=message; $('toast').hidden=false; clearTimeout(toast.timer); toast.timer=setTimeout(()=>$('toast').hidden=true,5000); }
async function api(url, options={}) {
  const response=await fetch(url,{...options,headers:{...(options.body && !(options.body instanceof File) ? {'Content-Type':'application/json'}:{}),...options.headers}});
  if (!response.ok) {
    let message='Não foi possível concluir a operação. Tente novamente.';
    try { const body=await response.json(); message=Array.isArray(body.detail) ? body.detail.map(x=>x.msg).join(' · ') : body.detail || message; } catch {}
    throw new Error(message);
  }
  return /application\/pdf|image\/png/.test(response.headers.get('content-type') || '') ? response.blob() : response.json();
}
function showResults(results) {
  $('metric-enel').textContent=money(results?.enel_bill);
  $('metric-zeta').textContent=money(results?.zeta_bill);
  $('metric-discount').textContent=money(results?.discount_total);
  $('calculated-details').replaceChildren();
  const details={consumption:'Consumo (kWh)',supply_rate:'Tarifa de fornecimento',injected_rate:'Tarifa de injeção',gd1_rate:'Tarifa GD1',gd2_rate:'Tarifa GD2',used_credits:'Créditos utilizados (kWh)',total:'Total de fornecimento',discount_current:'Desconto percentual',discount_flag:'Desconto bandeira',electricity_rate:'Valor da eletricidade / kWh'};
  for (const [key,label] of Object.entries(details)) {
    if (!results || results[key] == null) continue;
    const dt=document.createElement('dt'), dd=document.createElement('dd');dt.textContent=label;dd.textContent=['total','discount_current','discount_flag'].includes(key)?money(results[key]):numeric(results[key],8);$('calculated-details').append(dt,dd);
  }
}
function clearPreview(message) {
  $('pdf-preview').hidden=true;
  $('pdf-preview').removeAttribute('src');
  if (previewUrl) { URL.revokeObjectURL(previewUrl); previewUrl=null; }
  $('preview-placeholder').hidden=false;
  $('preview-placeholder').querySelector('p').textContent=message || 'Preencha os campos e o vencimento para visualizar o documento.';
}
function setPreview(blob) {
  const old=previewUrl; previewUrl=URL.createObjectURL(blob);
  $('pdf-preview').src=previewUrl;
  $('pdf-preview').hidden=false; $('preview-placeholder').hidden=true;
  if (old) URL.revokeObjectURL(old);
}
function updateButtons() {
  const eligible=!!state.client && state.invoice?.editable !== false && $('reference').checkValidity() && $('reference').value===state.reference;
  $('save-invoice').disabled=saving || !eligible || !state.calculation || !$('invoice-form').checkValidity();
  $('download-pdf').disabled=saving || !eligible || !state.invoice || state.dirty || !state.invoice.due_date;
  $('save-state').textContent=state.dirty?'Não salvo':state.invoice?'Salvo':'Novo mês';
  $('save-state').classList.toggle('dirty',state.dirty);
  $('save-hint').textContent=saving?'Salvando…':state.dirty?'Alterações ainda não salvas':state.invoice?'Registro salvo no histórico':'Preencha os dados do mês';
  $('preview-caption').textContent=state.dirty?'Prévia com alterações não salvas':'Modelo baseado na fatura ZetaGD';
}
function profile() { return state.profiles[state.invoice?.client?.rule || state.client?.rule || 'spec']; }
function inputs() { return Object.fromEntries(profile().fields.map(key=>[key,$(`field-${key}`).value])); }
function formData() { return {client_id:state.client.id,reference:state.reference,due_date:$('due-date').value,inputs:inputs(),flag_label:$('flag-label').value,notes:$('notes').value,payment_image:state.payment,version:state.version}; }
function stash() { if (state.client && state.dirty) drafts.set(draftKey(),formData()); }
function markDirty() { state.dirty=true; stash(); state.calculation=null; updateButtons(); clearPreview('Atualizando a prévia…'); scheduleCalculation(); }
function renderClients() {
  const query=$('search').value.toLocaleLowerCase('pt-BR');
  $('client-count').textContent=state.clients.length;
  $('clients').replaceChildren();
  for (const client of state.clients.filter(c=>(c.name+' '+c.legal_name).toLocaleLowerCase('pt-BR').includes(query))) {
    const button=document.createElement('button');button.className='client-button'+(state.client?.id===client.id?' selected':'');button.type='button';button.setAttribute('aria-pressed',String(state.client?.id===client.id));
    const avatar=document.createElement('span');avatar.className='mini-avatar';avatar.textContent=initials(client.name);
    const name=document.createElement('span');name.textContent=client.name;
    const chevron=document.createElement('span');chevron.className='chevron';chevron.textContent='›';chevron.setAttribute('aria-hidden','true');
    button.append(avatar,name,chevron);button.addEventListener('click',()=>selectClient(client.id,state.reference));$('clients').append(button);
  }
}
function buildFields(values={}) {
  $('dynamic-fields').replaceChildren();
  const sections=[['Consumo e créditos',['consumption','enel_consumption','panel_consumption','balance_credits','current_credits','grid_credits','credits_gd1','credits_gd2']],['Tarifas da distribuidora',['te_supply','tusd_supply','te_injected','tusd_injected','te','tusd','tusd_gd1','tusd_gd2','flag']],['Valores e desconto',['enel_bill','public_fees','discount_percent']]];
  let count=0;
  for (const [title,keys] of sections) {
    const visible=keys.filter(key=>profile().fields.includes(key));if (!visible.length) continue;
    const section=document.createElement('section');section.className='field-section';const heading=document.createElement('h4');const n=document.createElement('span');n.className='section-number';n.textContent=++count;heading.append(n,document.createTextNode(title));section.append(heading);
    const grid=document.createElement('div');grid.className='fields';
    for (const key of visible) {
      const label=document.createElement('label');label.textContent=state.labels[key];
      const input=document.createElement('input');input.id='field-'+key;input.name=key;input.required=true;input.inputMode='decimal';input.autocomplete='off';input.placeholder=key.includes('te')||key.includes('tusd')||key==='flag'?'0,00000':'0,00';input.maxLength=30;
      input.value=values[key] == null ? (key==='discount_percent'?state.client.discount_percent.replace('.',','):'') : String(values[key]).replace('.',',');
      label.append(input);grid.append(label);
    }
    section.append(grid);$('dynamic-fields').append(section);
  }
  $('rule-name').textContent=profile().name;
  $('rule-note').textContent=profile().note;
}
async function refreshHistory(cid, token) {
  const rows=await api(`/api/clients/${cid}/invoices`);
  if (token!==navigation) return;
  $('history-count').textContent=rows.length;
  $('history-rows').replaceChildren();
  for (const item of rows) {
    const tr=document.createElement('tr'), period=document.createElement('td'), amount=document.createElement('td'), discount=document.createElement('td');
    const button=document.createElement('button');button.textContent=monthName(item.reference);button.addEventListener('click',()=>{activateTab('data');selectClient(cid,item.reference);});
    const source=document.createElement('small');source.textContent=item.source==='spreadsheet'?'Importado da planilha':'Salvo na aplicação';period.append(button,source);amount.textContent=money(item.results.zeta_bill);discount.textContent=money(item.results.discount_total);tr.append(period,amount,discount);$('history-rows').append(tr);
  }
  if (!rows.length) {const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=3;td.textContent='Nenhuma fatura salva para este cliente.';tr.append(td);$('history-rows').append(tr);}
}
async function selectClient(cid, reference) {
  stash(); const token=++navigation; ++calculationSequence; clearTimeout(timer);requestController?.abort();
  clearPreview();notice('global-error','');showResults(null);$('save-invoice').disabled=true;$('download-pdf').disabled=true;
  try {
    const data=await api(`/api/invoices/${cid}/${reference}`);
    if (token!==navigation) return;
    state.client=data.client;state.reference=reference;state.invoice=data.invoice;state.version=data.invoice?.version || 0;state.calculation=null;state.dirty=false;
    $('reference').value=reference;
    $('client-name').textContent=data.client.name;
    $('client-detail').textContent=data.client.legal_name || 'Complete os dados cadastrais antes de emitir o PDF';
    $('client-avatar').textContent=initials(data.client.name);
    const draft=drafts.get(draftKey()), values=draft || data.invoice;
    state.version=draft?.version ?? data.invoice?.version ?? 0;
    buildFields(values?.inputs || {});
    $('due-date').value=values?.due_date || '';$('flag-label').value=values?.flag_label || '';$('notes').value=values?.notes || '';state.payment=values?.payment_image || null;setPaymentName(state.payment?'Imagem anexada ao registro':'');
    const historical=data.invoice?.editable === false;$('invoice-fields').disabled=historical;$('historical-notice').hidden=!historical;
    notice('calculation-error','');notice('warnings','');state.dirty=!!draft;
    $('workspace').hidden=false;$('empty-state').hidden=true;renderClients();showResults(data.invoice?.results);updateButtons();
    refreshHistory(cid,token).catch(error=>notice('global-error',error.message));
    if (historical) clearPreview('Este mês contém dados históricos. Consulte os valores originais na aba Histórico.');
    else scheduleCalculation(false);
  } catch (error) {if(token===navigation) notice('global-error',error.message);}
}
function scheduleCalculation(showError=true) {
  clearTimeout(timer); const token=++calculationSequence; requestController?.abort();
  if (!state.client || state.invoice?.editable === false) return;
  const values=inputs();
  if (Object.values(values).some(value=>!value.trim())) {state.calculation=null;if(state.dirty)showResults(null);updateButtons();clearPreview();return;}
  timer=setTimeout(async()=>{
    requestController=new AbortController();const signal=requestController.signal;
    try {
      const data=await api('/api/calculate',{method:'POST',body:JSON.stringify({inputs:values,client_id:state.client.id,reference:state.reference}),signal});
      if(token!==calculationSequence)return;
      state.calculation=data;showResults(data.results);notice('calculation-error','');notice('warnings',data.warnings.join(' '));updateButtons();
      if ($('invoice-form').checkValidity()) {
        const blob=await api('/api/preview.png',{method:'POST',body:JSON.stringify(formData()),signal});
        if(token===calculationSequence)setPreview(blob);
      } else clearPreview('Informe o vencimento para visualizar o documento.');
    } catch(error) {
      if(error.name==='AbortError'||token!==calculationSequence)return;
      state.calculation=null;showResults(null);updateButtons();clearPreview('Confira os campos indicados para gerar a prévia.');
      if(showError || state.invoice)notice('calculation-error',error.message);
    }
  },350);
}
async function loadBootstrap(preferredId, preferredReference) {
  const data=await api('/api/bootstrap');state.clients=data.clients;state.profiles=data.profiles;state.labels=data.labels;
  $('client-rule').replaceChildren();for(const [key,value]of Object.entries(data.profiles)){const option=document.createElement('option');option.value=key;option.textContent=value.name;$('client-rule').append(option);}
  if(!data.clients.length){state.client=null;$('empty-state').hidden=false;$('workspace').hidden=true;$('reference').value=data.latest_reference;renderClients();return;}
  const selected=data.clients.find(c=>c.id===preferredId)||data.clients.find(c=>c.name==='Icaraí')||data.clients[0];
  await selectClient(selected.id,preferredReference||selected.latest_reference||data.latest_reference);
}
function activateTab(tab) {
  const data=tab==='data';$('data-panel').hidden=!data;$('history-panel').hidden=data;
  for(const key of ['data','history']){const selected=key===tab;$('tab-'+key).classList.toggle('selected',selected);$('tab-'+key).setAttribute('aria-selected',selected);}
}
function setPaymentName(name){$('payment-status').hidden=!name;$('payment-name').textContent=name;}
function openClient(client=null){
  editorId=client?.id||null;$('dialog-title').textContent=client?'Editar cliente':'Novo cliente';$('client-form').reset();
  for(const key of ['name','legal_name','document','installation','address','discount_percent','rule'])$('client-form').elements[key].value=client?.[key] || (key==='discount_percent'?'10':key==='rule'?'spec':'');
  notice('client-error','');$('client-dialog').showModal();
}
$('client-form').addEventListener('submit',async event=>{
  event.preventDefault();const button=event.submitter;button.disabled=true;
  try{
    const body=Object.fromEntries(new FormData(event.target));body.version=editorId?state.client.version:0;
    const result=await api(editorId?`/api/clients/${editorId}`:'/api/clients',{method:editorId?'PUT':'POST',body:JSON.stringify(body)});
    $('client-dialog').close();toast('Cadastro salvo. Faturas anteriores mantêm os dados originais.');
    if(editorId) {stash();state.dirty=false;}
    await loadBootstrap(result.id,editorId?state.reference:undefined);
  }catch(error){notice('client-error',error.message);}finally{button.disabled=false;}
});
$('save-invoice').addEventListener('click',async()=>{
  if(!$('invoice-form').reportValidity())return;
  saving=true;updateButtons();const token=navigation;const body=formData();$('invoice-fields').disabled=true;
  try{
    const result=await api('/api/invoices',{method:'PUT',body:JSON.stringify(body)});
    drafts.delete(`${body.client_id}:${body.reference}`);
    if(token===navigation){state.invoice=result;state.version=result.version;state.dirty=false;updateButtons();await refreshHistory(state.client.id,token);}
    toast('Fatura salva no histórico. O PDF está disponível para baixar.');
  }catch(error){notice('calculation-error',error.message);}finally{saving=false;$('invoice-fields').disabled=state.invoice?.editable===false;updateButtons();}
});
$('download-pdf').addEventListener('click',async()=>{
  const button=$('download-pdf');button.disabled=true;
  try{const blob=await api(`/api/invoices/${state.client.id}/${state.reference}/pdf`);const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=`${state.client.name}-fatura-ZetaGD-${state.reference}.pdf`;link.click();setTimeout(()=>URL.revokeObjectURL(url),3000);toast('PDF gerado. O envio ao cliente é manual.');}catch(error){notice('calculation-error',error.message);}finally{updateButtons();}
});
async function importFile(file) {
  if(!file)return;if(!file.name.toLowerCase().endsWith('.xlsx')||file.size>10*1024*1024){notice('global-error','Use uma planilha XLSX com até 10 MB.');return;}
  $('import-button').disabled=true;$('empty-import').disabled=true;toast('Importando clientes e histórico…');
  try{const result=await api('/api/import',{method:'POST',body:file,headers:{'Content-Type':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}});await loadBootstrap(state.client?.id,state.reference||undefined);const skipped=result.sheets.reduce((n,s)=>n+s.skipped_missing,0);toast(`${result.added} registros importados. ${result.skipped} registros existentes preservados.${skipped?' '+skipped+' linhas sem dados completos ficaram fora.':''}`);}catch(error){notice('global-error',error.message);}finally{$('import-file').value='';$('import-button').disabled=false;$('empty-import').disabled=false;}
}
$('import-file').addEventListener('change',event=>importFile(event.target.files[0]));
for(const id of ['import-button','empty-import'])$(id).addEventListener('click',()=>$('import-file').click());
$('payment-file').addEventListener('change',async event=>{
  const file=event.target.files[0];if(!file)return;const token=navigation;
  if(!['image/png','image/jpeg'].includes(file.type)||file.size>1_400_000){notice('calculation-error','Use PNG ou JPG com até 1,4 MB.');event.target.value='';return;}
  const reader=new FileReader();reader.onload=()=>{if(token!==navigation)return;state.payment=reader.result;setPaymentName(file.name);markDirty();};reader.readAsDataURL(file);event.target.value='';
});
$('remove-payment').addEventListener('click',()=>{state.payment=null;setPaymentName('');markDirty();});
$('invoice-form').addEventListener('input',event=>{if(event.target.type!=='file')markDirty();});
$('invoice-form').addEventListener('submit',event=>event.preventDefault());
$('search').addEventListener('input',renderClients);
$('reference').addEventListener('change',()=>{
  if(state.client&&$('reference').validity.valid)selectClient(state.client.id,$('reference').value);
  else {updateButtons();clearPreview('Selecione um mês de referência válido.');}
});
$('new-client').addEventListener('click',()=>openClient());$('edit-client').addEventListener('click',()=>openClient(state.client));
for(const id of ['close-dialog','cancel-dialog'])$(id).addEventListener('click',()=>$('client-dialog').close());
$('tab-data').addEventListener('click',()=>activateTab('data'));$('tab-history').addEventListener('click',()=>activateTab('history'));
window.addEventListener('beforeunload',event=>{if(state.dirty||drafts.size){event.preventDefault();event.returnValue='';}});
loadBootstrap().catch(error=>notice('global-error',error.message));
