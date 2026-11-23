'use strict';
const $ = id => document.getElementById(id);
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state = {bootstrap:null, files:[], current:null, detail:null, active:null, pending:null, pollBusy:false};
const statusNames = {queued:'Queued',running:'Generating',completed:'Generated',failed:'Generation failed',interrupted:'Interrupted'};
const toolNames = {retrieve_uploaded_documents:'Retrieve uploaded documents',web_search:'Search the web',web_fetch:'Read web content',
  sec_filings:'Find SEC filings',sec_company_facts:'Retrieve SEC company facts',tushare_query:'Query Tushare',alpha_vantage:'Query Alpha Vantage',write_file:'Save report'};
const eventNames = {model_started:'Model request started',model_completed:'Model response completed',tool_completed:'Tool call completed',tool_failed:'Tool call failed'};
function mode(){return document.querySelector('input[name=source_mode]:checked').value;}
function error(message){$('form-error').textContent=message;$('form-error').hidden=!message;}
async function api(path, options={}){
  const response=await fetch(path,{...options,headers:{'Content-Type':'application/json',...options.headers}});
  const value=await response.json();
  if(!response.ok)throw new Error(value.error||'Request failed. Please try again.');
  return value;
}
function inline(text){
  const regex=/`([^`]+)`|\*\*([^*]+)\*\*|\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|\[S\d+\]/g;
  let html='',last=0;
  for(const match of text.matchAll(regex)){
    html+=escapeHTML(text.slice(last,match.index));
    if(match[1])html+='<code>'+escapeHTML(match[1])+'</code>';
    else if(match[2])html+='<strong>'+escapeHTML(match[2])+'</strong>';
    else if(match[3])html+='<a href="'+escapeHTML(match[4])+'" target="_blank" rel="noopener noreferrer">'+escapeHTML(match[3])+'</a>';
    else html+='<button class="citation" data-citation="'+escapeHTML(match[0])+'" title="Inspect source evidence">'+escapeHTML(match[0])+'</button>';
    last=match.index+match[0].length;
  }
  return html+escapeHTML(text.slice(last));
}
// Deliberately render text-only Markdown: no raw HTML, images or executable URLs.
function markdown(text){
  const lines=text.split('\n');let html='',list=null;
  const closeList=()=>{if(list){html+='</'+list+'>';list=null;}};
  const cells=line=>line.trim().replace(/^\||\|$/g,'').split('|').map(s=>s.trim());
  for(let i=0;i<lines.length;i++){
    let line=lines[i];
    if(!line.trim()){closeList();continue;}
    if(/^```/.test(line)){
      closeList();let code=[];while(++i<lines.length&&!/^```/.test(lines[i]))code.push(lines[i]);
      html+='<pre><code>'+escapeHTML(code.join('\n'))+'</code></pre>';continue;
    }
    const heading=line.match(/^(#{1,6})\s+(.+)$/);
    if(heading){closeList();html+='<h'+heading[1].length+'>'+inline(heading[2])+'</h'+heading[1].length+'>';continue;}
    if(line.includes('|')&&i+1<lines.length&&/^\s*\|?\s*:?-{3,}/.test(lines[i+1])){
      closeList();html+='<table><thead><tr>'+cells(line).map(c=>'<th>'+inline(c)+'</th>').join('')+'</tr></thead><tbody>';i++;
      while(i+1<lines.length&&lines[i+1].includes('|')){
        html+='<tr>'+cells(lines[++i]).map(c=>'<td>'+inline(c)+'</td>').join('')+'</tr>';
      }html+='</tbody></table>';continue;
    }
    const item=line.match(/^\s*(?:[-*+]|\d+[.)])\s+(.+)$/);
    if(item){
      const type=/^\s*\d/.test(line)?'ol':'ul';if(list!==type){closeList();list=type;html+='<'+list+'>';}
      html+='<li>'+inline(item[1])+'</li>';continue;
    }
    closeList();
    let paragraph=line;
    while(i+1<lines.length&&lines[i+1].trim()&&!/^(#{1,6}\s|```|\s*[-*+]\s|\s*\d+[.)]\s)/.test(lines[i+1])
          &&!(lines[i+1].includes('|')&&/^\s*\|?\s*:?-{3,}/.test(lines[i+2]||'')))paragraph+=' '+lines[++i];
    html+='<p>'+inline(paragraph)+'</p>';
  }closeList();return html;
}
function switchTab(name){
  document.querySelectorAll('.tab').forEach(button=>{
    const selected=button.dataset.tab===name;button.classList.toggle('active',selected);
    button.setAttribute('aria-selected',String(selected));button.tabIndex=selected?0:-1;
  });
  document.querySelectorAll('.panel').forEach(panel=>panel.hidden=panel.id!=='panel-'+name);
}
function updateMode(){
  const selected=mode();
  $('document-controls').hidden=selected==='web_only';
  $('finance-note').hidden=selected==='uploaded_only';
  $('mode-help').textContent={uploaded_only:'Use only your selected documents as report evidence.',
    hybrid:'The report body must cite both document and web evidence.',
    web_only:'Use web pages and financial APIs. Selected documents are excluded.'}[selected];
  updateButton();
}
function updateButton(){
  const service=state.bootstrap?.services;
  const unavailable=service&&(!service.model||(mode()!=='web_only'&&!service.embedding));
  $('generate').disabled=Boolean(state.active||unavailable);
  $('generate').innerHTML=state.active?'Generating report…':'Generate report <span>↗</span>';
  $('service-note').textContent=unavailable?'Service configuration is missing. Configure the model and required embedding service, then restart.':'Up to 8 model calls · Word limits only when requested';
}
function updateSelections(){
  const count=document.querySelectorAll('#corpus-options input:checked').length;
  $('selected-count').textContent=count+' selected';
  $('uploaded-files').innerHTML=state.files.map((file,i)=>'<div class="uploaded-file"><span>▧ '+escapeHTML(file.name)+'</span><small>'+Math.ceil(file.size/1024)+' KB</small><button type="button" data-remove="'+i+'" aria-label="Remove '+escapeHTML(file.name)+'">×</button></div>').join('');
}
async function addFiles(files){
  error('');
  for(const file of files){
    if(!/\.(txt|md)$/i.test(file.name)){error('Choose TXT or Markdown files.');return;}
    if(state.files.length>=4){error('Upload up to 4 files per report.');return;}
    if(state.files.reduce((n,f)=>n+f.size,0)+file.size>1000000){error('Uploaded files must total no more than 1 MB.');return;}
    state.files.push(file);
  }updateSelections();
}
function showSource(citation){
  const source=state.detail?.sources.find(s=>s.citation===citation);
  if(!source)return;
  let text=source.text||'';
  if(source.access_method==='financial_api'){try{text=JSON.stringify(JSON.parse(text),null,2);}catch{}}
  const url=/^https?:\/\//.test(source.source_url||'')?source.source_url:null;
  const mapping=state.detail.job.input_mapping?.find(m=>m.document_id===source.document_id);
  $('source-detail').innerHTML='<h2>'+escapeHTML(citation+' '+source.title)+'</h2><div class="source-meta">'+
    escapeHTML(source.access_method==='financial_api'?'Structured financial data':source.source_kind==='uploaded'?'Uploaded document':'Web content')+
    (mapping?'<br>File: '+escapeHTML(mapping.original_name):'')+
    '<br>Character range ['+source.char_start+', '+source.char_end+')'+
    (source.retrieved_at?'<br>Retrieved at: '+escapeHTML(source.retrieved_at):'')+
    '<br>SHA-256：'+escapeHTML(source.excerpt_sha256||source.text_sha256)+'</div>'+
    (url?'<a href="'+escapeHTML(url)+'" target="_blank" rel="noopener noreferrer">Open original source ↗</a>':'')+
    '<pre>'+escapeHTML(text)+'</pre><p class="help">This is the evidence actually supplied to the model. Valid citations and successful retrieval do not establish factual correctness.</p>';
  $('source-dialog').showModal();
}
function checkRow(label,passed,detail=''){
  return '<div class="check-row"><span>'+escapeHTML(label)+(detail?' · '+escapeHTML(detail):'')+'</span><span class="check-state '+(passed===false?'fail':'')+'">'+
    (passed===true?'✓ Pass':passed===false?'Needs review':'Not checked')+'</span></div>';
}
function renderDetail(data){
  state.detail=data;const job=data.job,summary=data.summary,audit=data.audit||{},running=['queued','running'].includes(job.status);
  $('run-label').textContent=job.historical_example?'SAVED EXAMPLE · Read-only example':'REPORT / '+job.id.slice(-8);
  $('workspace-title').textContent=running?'Generating your report':'Report preview';
  $('run-badge').textContent=running?'Generating':job.status==='completed'?(audit.automatic_passed?'Generated · Checks passed':'Generated · Needs review'):statusNames[job.status]||'Ready';
  $('run-badge').className='badge'+(job.status==='failed'||job.status==='interrupted'?' error-badge':job.status==='completed'&&!audit.automatic_passed?' warning':'');
  $('progress').hidden=!running;
  if(running){
    const last=data.events.at(-1),lastTool=[...data.events].reverse().find(e=>e.type==='tool_requested');
    $('progress-title').textContent=data.model_attempts?'The model is processing your task':'Preparing the run and sources';
    if(last?.type==='tool_requested')$('progress-title').textContent=toolNames[last.name]||last.name;
    $('progress-detail').textContent='Started '+data.model_attempts+' model requests'+(lastTool?' · Latest tool: '+(toolNames[lastTool.name]||lastTool.name):'');
    $('elapsed').textContent=Math.max(0,Math.floor((Date.now()-Date.parse(job.created_at))/1000))+'s';
  }
  const note=job.error|| (job.historical_example?'This is a saved report from a real run. Viewing it makes no model requests.':'')||
    (job.status==='completed'&&!audit.automatic_passed?'The report is saved, but some automatic checks failed. Open Quality checks for details; the original result is retained.':'');
  $('result-note').hidden=!note;$('result-note').textContent=note;
  $('report-empty').hidden=Boolean(data.report);
  $('report-content').hidden=!data.report;
  // Preserve reading position and focused citation buttons between polls.
  if($('report-content').dataset.report!==data.report){$('report-content').innerHTML=markdown(data.report);$('report-content').dataset.report=data.report;}
  $('source-count').textContent=data.sources.length;
  $('source-list').innerHTML=data.sources.length?data.sources.map(source=>
    '<button class="source-card" data-citation="'+escapeHTML(source.citation)+'"><div><span class="citation">'+escapeHTML(source.citation)+'</span><strong>'+
    escapeHTML(source.title)+'</strong><span class="source-type">'+(source.source_kind==='uploaded'?'Document':source.access_method==='financial_api'?'Financial API':'Web page')+
    '</span></div><p>'+escapeHTML(source.source_url||source.document_id)+'</p><p>View evidence · '+(source.char_end-source.char_start).toLocaleString()+' characters ↗</p></button>').join(''):
    '<p class="help">No sources retrieved yet. Evidence will appear here during generation.</p>';
  const usage=summary.usage,custom=audit.customization,auto=audit.automatic;
  $('checks-content').innerHTML='<div class="metrics"><div class="metric"><strong>'+data.sources.length+'</strong><span>Evidence excerpts</span></div><div class="metric"><strong>'+
    (custom?.body_words??custom?.items.find(i=>i.id==='depth_words')?.observed??'—')+'</strong><span>Report words</span></div><div class="metric"><strong>'+
    (usage?.total_tokens?.toLocaleString()??'—')+'</strong><span>Recorded tokens</span></div></div>'+
    checkRow('Structure and citation format',auto?.mechanical_checks_passed)+checkRow('Source mode',audit.source_mode_passed)+
    checkRow('Selected documents cited in body',audit.selected_document_body_coverage)+checkRow('Customization constraints',custom?.passed)+
    (custom?.items||[]).map(item=>checkRow(item.id==='depth_words'?'Word range':item.id,item.passed,JSON.stringify(item.observed)+' / '+JSON.stringify(item.expected))).join('')+
    '<div class="note-block">Factual support: '+(audit.factual_support_validated?'audit recorded':'independent human audit pending')+'. Automatic checks assess format, word count and source references, not the truth of every claim.</div>'+
    (data.development_review?'<div class="note-block"><strong>Saved development spot check</strong><p>Asset balances and growth calculations were checked. The raw report confused the query cutoff with the retrieval date; the displayed sources use the logged timestamp. The year-on-year difference is a derived value.</p>This assistant development check is not an independent human rating.</div>':'');
  const tools=data.events.filter(e=>e.type==='tool_requested');
  const events=data.events.length?data.events:data.tools.map(t=>({type:'tool_requested',name:t.name,at:t.started_at}));
  $('activity-content').innerHTML='<div class="metrics"><div class="metric"><strong>'+data.model_attempts+'</strong><span>Model requests / max. 8</span></div><div class="metric"><strong>'+
    (summary.elapsed_seconds!==undefined?summary.elapsed_seconds.toFixed(1)+'s':'—')+'</strong><span>Elapsed time</span></div><div class="metric"><strong>'+
    (summary.embedding_calls??'—')+'</strong><span>New embedding calls</span></div></div>'+
    (events.length?events.map((e,i)=>'<div class="activity-row"><span>'+String(i+1).padStart(2,'0')+'</span><div>'+
      escapeHTML(e.type==='tool_requested'?toolNames[e.name]||e.name:eventNames[e.type]||e.type)+'</div><small>'+
      (typeof e.at==='number'?'+'+e.at.toFixed(2)+'s':e.at?escapeHTML(new Date(e.at).toLocaleTimeString('en-GB',{hour12:false})):'')+'</small></div>').join(''):'<p class="help">Actual runtime events appear here once the run starts.</p>')+
    '<div class="version-block">Run ID<code>'+escapeHTML(job.id)+'</code>System version<code>'+escapeHTML(data.versions.code||'Not recorded yet')+'</code></div>';
  $('report-meta').textContent=summary.elapsed_seconds!==undefined?'Elapsed '+summary.elapsed_seconds.toFixed(1)+'s · '+(summary.model_calls??data.model_attempts)+' model requests':'Clickable citations · Traceable sources';
  for(const [id,kind] of [['download-report','report'],['download-raw','raw'],['download-bundle','bundle']]){
    $(id).hidden=running||(kind!=='bundle'&&!data.report);
    $(id).href='/api/jobs/'+job.id+'/download/'+kind;$(id).setAttribute('download','');
  }
}
async function selectJob(id){
  state.current=id;localStorage.setItem('report-studio-selected',id);
  const data=await api('/api/jobs/'+id);
  if(state.current===id)renderDetail(data);
}
async function refreshHistory(){
  const jobs=await api('/api/jobs');
  state.active=jobs.find(j=>['queued','running'].includes(j.status))?.id||null;
  $('history-count').textContent=jobs.length;
  if(state.historySignature!==JSON.stringify(jobs)){
    state.historySignature=JSON.stringify(jobs);
    $('history').innerHTML=jobs.length?jobs.map(job=>'<button class="history-item" data-job="'+escapeHTML(job.id)+'"><strong>'+escapeHTML(job.title)+'</strong><small>'+
    escapeHTML(statusNames[job.status]||job.status)+' · '+escapeHTML(new Date(job.created_at).toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit',hour12:false}))+'</small></button>').join(''):'<p class="muted">No reports yet</p>';
  }
  updateButton();return jobs;
}
function fillExample(){
  $('task').value='Summarise NVIDIA FY2025 data center performance and AI infrastructure strategy, using the selected CFO commentary. Distinguish annual and Q4 results, cite evidence, and state limitations. Keep the report within 250–500 words.';
  document.querySelector('input[name=source_mode][value=uploaded_only]').checked=true;
  document.querySelectorAll('#corpus-options input').forEach(input=>input.checked=input.value==='nvidia_fy2025_q4_cfo_commentary');
  $('structure').value='standard_analysis';$('style').value='formal_analytical';$('depth').value='brief';
  $('task-count').textContent=$('task').value.length+' / 4000';$('corpus-options').parentElement.open=true;updateMode();updateSelections();
}
async function filePayload(file){
  const bytes=new Uint8Array(await file.arrayBuffer());
  let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));
  return {name:file.name,data:btoa(binary)};
}
$('report-form').addEventListener('submit',async event=>{
  event.preventDefault();error('');
  if(state.active)return;
  const selectedMode=mode();
  const documents=selectedMode==='web_only'?[]:[...document.querySelectorAll('#corpus-options input:checked')].map(i=>i.value);
  if(selectedMode!=='web_only'&&!documents.length&&!state.files.length){error('Select example documents or upload at least one file.');return;}
  if(documents.length+(selectedMode==='web_only'?0:state.files.length)>4){error('Select or upload no more than 4 documents in total.');return;}
  $('generate').disabled=true;
  try{
    const payload={request:{task:$('task').value.trim(),source_mode:selectedMode,structure:$('structure').value,style:$('style').value,depth:$('depth').value,
      min_words:$('min-words').value?Number($('min-words').value):null,max_words:$('max-words').value?Number($('max-words').value):null},
      documents,uploads:selectedMode==='web_only'?[]:await Promise.all(state.files.map(filePayload))};
    const signature=JSON.stringify(payload);
    if(state.pending?.signature!==signature)state.pending={signature,id:crypto.randomUUID().replaceAll('-','')};
    payload.submission_id=state.pending.id;
    const result=await api('/api/jobs',{method:'POST',headers:{'X-Report-Token':state.bootstrap.token},body:JSON.stringify(payload)});
    state.active=result.id;state.pending=null;switchTab('report');await selectJob(result.id);await refreshHistory();
  }catch(exc){error(exc.message);}finally{updateButton();}
});
document.querySelectorAll('input[name=source_mode]').forEach(input=>input.addEventListener('change',updateMode));
$('task').addEventListener('input',()=>{$('task-count').textContent=$('task').value.length+' / 4000';});
$('file-input').addEventListener('change',async event=>{await addFiles(event.target.files);event.target.value='';});
$('upload-zone').addEventListener('dragover',event=>{event.preventDefault();$('upload-zone').classList.add('dragging');});
$('upload-zone').addEventListener('dragleave',()=>{$('upload-zone').classList.remove('dragging');});
$('upload-zone').addEventListener('drop',event=>{event.preventDefault();$('upload-zone').classList.remove('dragging');addFiles(event.dataTransfer.files);});
$('uploaded-files').addEventListener('click',event=>{const button=event.target.closest('[data-remove]');if(button){state.files.splice(Number(button.dataset.remove),1);updateSelections();}});
$('corpus-options').addEventListener('change',updateSelections);
document.querySelectorAll('.tab').forEach(button=>button.addEventListener('click',()=>switchTab(button.dataset.tab)));
document.querySelector('.tabbar').addEventListener('keydown',event=>{
  if(!['ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
  const tabs=[...document.querySelectorAll('.tab')],index=tabs.indexOf(document.activeElement);
  if(index<0)return;event.preventDefault();
  const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
  switchTab(tabs[next].dataset.tab);tabs[next].focus();
});
document.querySelector('.workspace').addEventListener('click',event=>{const button=event.target.closest('[data-citation]');if(button)showSource(button.dataset.citation);});
$('close-source').addEventListener('click',()=>$('source-dialog').close());
$('source-dialog').addEventListener('click',event=>{if(event.target===$('source-dialog'))$('source-dialog').close();});
$('history').addEventListener('click',event=>{const button=event.target.closest('[data-job]');if(button){document.querySelector('.sidebar').classList.remove('show-history');$('mobile-history').setAttribute('aria-expanded','false');switchTab('report');selectJob(button.dataset.job).catch(e=>error(e.message));}});
$('mobile-history').addEventListener('click',()=>{const shown=document.querySelector('.sidebar').classList.toggle('show-history');$('mobile-history').setAttribute('aria-expanded',String(shown));});
$('fill-example').addEventListener('click',fillExample);
for(const id of ['open-example','empty-example'])$(id).addEventListener('click',()=>{
  if(state.bootstrap?.example_id){switchTab('report');selectJob(state.bootstrap.example_id).catch(e=>error(e.message));}
});
$('new-task').addEventListener('click',()=>{
  $('task').focus();$('task').scrollIntoView({block:'center',behavior:'smooth'});error('');
});
async function init(){
  try{
    state.bootstrap=await api('/api/bootstrap');
    $('corpus-options').innerHTML=state.bootstrap.documents.map(doc=>'<label class="corpus-option"><input type="checkbox" value="'+escapeHTML(doc.id)+'"><span>'+
      escapeHTML(doc.title)+'<small>'+Math.ceil(doc.chars/1000)+'k characters · Archived example source</small></span></label>').join('');
    const jobs=await refreshHistory();updateMode();
    const saved=localStorage.getItem('report-studio-selected');
    const id=state.active||(jobs.some(j=>j.id===saved)?saved:null)||state.bootstrap.example_id;
    if(id)await selectJob(id);
    $('open-example').hidden=!state.bootstrap.example_id;$('empty-example').hidden=!state.bootstrap.example_id;
  }catch(exc){error('Cannot connect to the local report service: '+exc.message);}
}
setInterval(async()=>{
  if(state.pollBusy||!state.bootstrap)return;
  state.pollBusy=true;
  try{
    const wasActive=state.active;await refreshHistory();
    if(state.current&&(wasActive===state.current||state.active===state.current))await selectJob(state.current);
  }catch(exc){if(state.active)error('Connection interrupted. Your task will not be resubmitted automatically. Refresh to check its status.');}
  finally{state.pollBusy=false;}
},1500);
init();
