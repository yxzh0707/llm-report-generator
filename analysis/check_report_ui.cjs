// Local browser QA. --live submits exactly two development reports, never formal runs.
const fs=require('fs'),path=require('path'),assert=require('assert');
const puppeteer=require(process.env.REVIEW_PUPPETEER_MODULE||'puppeteer');
const base='http://localhost:8767',out=path.resolve('artifacts/verification/report_ui');
const live=process.argv.includes('--live');fs.mkdirSync(out,{recursive:true});
async function main(){
 const browser=await puppeteer.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 const errors=[],external=[],runs=[];
 const result={checked_at:new Date().toISOString(),live_requested:live,checks:[],runs};
 const save=()=>fs.writeFileSync(path.join(out,live?'live-result.json':'browser-result.json'),JSON.stringify(result,null,2)+'\n');
 try{
  const page=await browser.newPage();await page.setViewport({width:1440,height:1050});
  page.on('pageerror',e=>errors.push(e.message));await page.setRequestInterception(true);
  page.on('request',r=>{if(/^https?:/.test(r.url())&&new URL(r.url()).origin!==base){external.push(r.url());r.abort();}else r.continue();});
  assert.strictEqual((await page.goto(base,{waitUntil:'networkidle0'})).status(),200);
  await page.waitForSelector('#report-content:not([hidden])');
  await page.click('#open-example');await page.waitForFunction(()=>document.getElementById('run-label').textContent.includes('SAVED EXAMPLE'));
  await page.click('#report-content .citation');await page.waitForSelector('#source-dialog[open]');
  assert((await page.$eval('#source-detail',e=>e.textContent)).includes('111601000000'));
  await page.screenshot({path:path.join(out,'source-evidence.png'),fullPage:false});await page.click('#close-source');
  for(const tab of ['sources','checks','activity','report']){
   await page.click('[data-tab="'+tab+'"]');assert(await page.$eval('#panel-'+tab,e=>!e.hidden));
  }
  assert((await page.$eval('#activity-content',e=>e.textContent)).includes('+'));
  const safe=await page.evaluate(()=>{const node=document.createElement('div');node.innerHTML=markdown('<img src=x onerror=alert(1)>\n\n[bad](javascript:alert(1))');return !node.querySelector('img,script,a');});assert(safe);
  const downloads=await page.evaluate(async()=>{let values=[];for(const id of ['download-report','download-raw','download-bundle']){const r=await fetch(document.getElementById(id).href);const b=await r.arrayBuffer();values.push({status:r.status,size:b.byteLength});}return values;});
  assert(downloads.every(x=>x.status===200&&x.size>0));
  const stateChecks=await page.evaluate(()=>{
    const original=state.detail;
    renderDetail({...original,job:{...original.job,status:'failed',error:'Isolated UI failure fixture'},report:'',audit:{}});
    const failed=document.getElementById('run-badge').textContent==='Generation failed'&&document.getElementById('result-note').textContent.includes('Isolated UI failure fixture');
    renderDetail({...original,job:{...original.job,status:'completed'},audit:{...original.audit,automatic_passed:false}});
    const warning=document.getElementById('run-badge').textContent.includes('Needs review');
    renderDetail(original);return {failed,warning};
  });assert(stateChecks.failed&&stateChecks.warning);
  assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth));
  await page.screenshot({path:path.join(out,'desktop.png'),fullPage:true});
  await page.setViewport({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));
  assert(!await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth));
  await page.click('#mobile-history');assert.strictEqual(await page.$eval('#mobile-history',e=>e.getAttribute('aria-expanded')),'true');await page.click('#mobile-history');assert.strictEqual(await page.$eval('#mobile-history',e=>e.getAttribute('aria-expanded')),'false');
  await page.screenshot({path:path.join(out,'mobile.png'),fullPage:true});await page.setViewport({width:1440,height:1050});
  await page.type('#task','A task without selected evidence');await page.click('#generate');
  assert((await page.$eval('#form-error',e=>e.textContent)).includes('at least one'));
  result.checks=['HTTP 200','report rendered','citation opens exact financial evidence','all tabs','relative runtime timestamps','raw HTML and javascript URL not executed','failed and unchecked result states (isolated browser fixture)','report/raw/bundle downloads','desktop/mobile no horizontal overflow','mobile history accessible','empty-source submission rejected'];save();
  if(live){
   const file=await page.$('#file-input');await file.uploadFile(path.resolve('data/corpus/processed/nvidia_fy2025_q4_cfo_commentary.md'));
   await page.waitForSelector('.uploaded-file');
   const tasks=[
    {mode:'uploaded_only',task:'Using only the uploaded NVIDIA CFO commentary, summarise FY2025 and Q4 revenue, data center performance, and AI infrastructure demand. Distinguish annual and quarterly figures, cite all material facts, and state evidence gaps. Write 250–450 words.'},
    {mode:'hybrid',task:'Combine the uploaded NVIDIA FY2025 CFO commentary with SEC company facts to summarise revenue performance and the year-end balance sheet. Retrieve the uploaded document first. Then use sec_company_facts with identifier 1045810, concept Assets, before 2025-02-27, limit 2. Cite BOTH the uploaded commentary and the financial API data in the body. Distinguish annual and quarterly figures, USD and billions, period end and filing date. Use no other web discovery. Write 250–450 words and explain evidence limitations.'}
   ];
   for(const task of tasks){
    await page.click('input[name=source_mode][value='+task.mode+']');
    await page.$eval('#task',(e,text)=>{e.value=text;e.dispatchEvent(new Event('input',{bubbles:true}));},task.task);
    const response=page.waitForResponse(r=>r.url()===base+'/api/jobs'&&r.request().method()==='POST');
    await page.click('#generate');const submitted=await response;assert.strictEqual(submitted.status(),202);const {id}=await submitted.json();
    runs.push({id,mode:task.mode,status:'submitted'});save();
    await page.waitForFunction(async id=>{const data=await(await fetch('/api/jobs/'+id)).json();return ['completed','failed','interrupted'].includes(data.job.status);},{timeout:540000,polling:1500},id);
    const data=await page.evaluate(async id=>(await fetch('/api/jobs/'+id)).json(),id);
    Object.assign(runs.at(-1),{status:data.job.status,summary:data.summary,audit:data.audit,source_kinds:[...new Set(data.sources.map(s=>s.source_kind))],versions:data.versions});save();
    await page.waitForFunction(()=>!document.getElementById('generate').disabled,{timeout:10000});
    assert.strictEqual(data.job.status,'completed');assert(data.report.length>0);
    assert.deepStrictEqual(data.audit.body_cited_source_kinds,task.mode==='hybrid'?['uploaded','web']:['uploaded']);
    await page.reload({waitUntil:'networkidle0'});await page.waitForSelector('#report-content:not([hidden])');
    assert((await page.$eval('#run-label',e=>e.textContent)).includes(id.slice(-8)));
    await page.screenshot({path:path.join(out,task.mode+'.png'),fullPage:true});
    if(task.mode==='uploaded_only'){
      // Reload restores saved output; upload selection is deliberately not persisted.
      await(await page.$('#file-input')).uploadFile(path.resolve('data/corpus/processed/nvidia_fy2025_q4_cfo_commentary.md'));
    }
   }
   result.checks.push('real UTF-8 upload and generation','real hybrid document+financial API body citations','reload recovers report','first results preserved without revisions');
  }
  assert.deepStrictEqual(errors,[]);assert.deepStrictEqual(external,[]);
  result.passed=true;result.page_errors=errors;result.external_browser_requests=external;save();
  console.log(JSON.stringify(result));
 }catch(e){result.passed=false;result.error=e.message;result.page_errors=errors;save();throw e;}
 finally{await browser.close();}
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
