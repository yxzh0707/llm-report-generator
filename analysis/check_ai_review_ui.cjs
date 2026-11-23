// Check the local, single-file review UI in an isolated temporary Chrome profile.
// Any simulated human confirmations remain in that temporary profile only.
const fs=require('fs'),path=require('path'),assert=require('assert');
const puppeteer=require(process.env.REVIEW_PUPPETEER_MODULE||'puppeteer');
async function main(){
 const target=process.argv[2],isHttp=/^https?:\/\//.test(target);
 const html=isHttp?new URL(target).href:path.resolve(target),out=path.resolve(process.argv[3]);
 const allowedOrigin=isHttp?new URL(html).origin:null;
 fs.mkdirSync(out,{recursive:true});
 const browser=await puppeteer.launch({executablePath:process.env.REVIEW_CHROME||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true,args:['--no-sandbox','--allow-file-access-from-files']});
 const errors=[],network=[];try{
  const page=await browser.newPage();await page.setViewport({width:1280,height:1000});
  page.on('pageerror',e=>errors.push(e.message));await page.setRequestInterception(true);
  page.on('request',r=>{if(/^https?:/.test(r.url())&&new URL(r.url()).origin!==allowedOrigin){network.push(r.url());r.abort()}else r.continue()});
  const response=await page.goto(isHttp?html:'file://'+html,{waitUntil:'load'});
  if(isHttp)assert.strictEqual(response.status(),200);
  await page.waitForSelector('#question h2');
  assert((await page.$eval('#stats',e=>e.textContent)).includes('事实 0/20'));
  assert((await page.$eval('#question',e=>e.textContent)).includes('Q001'));
  await page.screenshot({path:path.join(out,'initial.png'),fullPage:true});
  await page.click('#accept');assert((await page.$eval('#notice',e=>e.textContent)).includes('评审者'));
  await page.type('#reviewer','isolated UI fixture; not a real human score');
  await page.click('#accept');assert((await page.$eval('#notice',e=>e.textContent)).includes('确认'));
  await page.click('#selection');await page.click('#accept');
  assert((await page.$eval('#question',e=>e.textContent)).includes('Q002'));
  assert((await page.$eval('#stats',e=>e.textContent)).includes('事实 1/20'));
  await page.evaluate(()=>{window.__exports=[];URL.createObjectURL=blob=>{window.__exports.push(blob.text());return 'blob:isolated-fixture'};URL.revokeObjectURL=()=>{};HTMLAnchorElement.prototype.click=function(){}});
  await page.click('#export');const exported=await page.evaluate(async()=>JSON.parse(await window.__exports[0]));
  assert.strictEqual(exported.schema,'actual-human-review-confirmations-v1');assert.strictEqual(exported.answers.length,1);
  assert.strictEqual(exported.answers[0].qid,'Q001');assert.strictEqual(exported.answers[0].selection_confirmed,true);
  assert(exported.answers[0].reviewed_evidence_ids.length>0);assert.strictEqual(typeof exported.answers[0].result_sha256,'string');
  await page.select('#filter','content');const contentItems=await page.$$eval('#jump option',o=>o.length);
  if(contentItems){
   assert(await page.$eval('#selectionRow',e=>e.hidden));
   await page.select('#humanLabel','not_satisfied');await page.type('#humanReason','Isolated UI override fixture only.');
   await page.click('#override');assert((await page.$eval('#stats',e=>e.textContent)).includes('内容/定制 1/123'));
  }
  const issuesExpected=await page.$eval('#review-data',e=>JSON.parse(e.textContent).items.filter(i=>['insufficient','uncertain','not_satisfied','contradicted'].includes(i.result.judgment)).length);
  await page.select('#filter','issues');assert.strictEqual(await page.$$eval('#jump option',o=>o.length),issuesExpected);
  await page.reload({waitUntil:'load'});assert((await page.$eval('#stats',e=>e.textContent)).includes('事实 1/20'));
  assert.deepStrictEqual(errors,[]);assert.deepStrictEqual(network,[]);
  const result={passed:true,real_human_scores_written:0,profile:'temporary and deleted on browser.close',
   checks:['Chinese question visible','no auto human scores','reviewer required','source sample confirmation required','explicit confirmation advances one item','export binds input/result hashes','human evidence IDs exported','local persistence works','issues filter matches saved labels','no page errors',isHttp?'HTTP 200; no external network requests':'no network requests'],
   content_questions_available:contentItems,content_override_checked:contentItems>0,html:html};
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,2)+'\n');process.stdout.write(JSON.stringify(result)+'\n');
 }finally{await browser.close()}
}
main().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1});
