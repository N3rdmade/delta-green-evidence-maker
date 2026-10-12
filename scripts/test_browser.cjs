const { chromium } = require((process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES ? process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES + '/playwright' : 'playwright'));
const fs = require('fs');
const assert = require('assert');
(async()=>{
 const browser = await chromium.launch({...(process.env.EVIDENCE_CHROME ? {executablePath:process.env.EVIDENCE_CHROME}:{}),headless:true,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1600,height:1000},acceptDownloads:true});
 const page=await context.newPage();
 const errors=[],failed=[];
 process.on('unhandledRejection',e=>{console.error(e);process.exit(1)});
 const deadline=setTimeout(async()=>{console.error('Test timed out; status:',await page.locator('#status').textContent());await page.screenshot({path:'test-results/failure.png'});process.exit(1)},180000);

 page.on('pageerror',e=>errors.push(e.message));
 page.on('response',r=>{if(r.status()>=400&&r.url().startsWith('http://127.0.0.1'))failed.push(r.status()+' '+r.url());});
 await page.goto(process.env.EVIDENCE_TEST_URL || 'http://127.0.0.1:8765/');
 await page.waitForFunction(()=>document.getElementById('status').textContent==='Ready');
 await page.waitForFunction(()=>document.getElementById('frameImg').naturalWidth>0);
 await page.evaluate(()=>document.fonts.ready);
 assert.strictEqual(await page.evaluate(()=>frameList.length),44);
 await page.evaluate(()=>loadStickers());
 assert.strictEqual(await page.evaluate(()=>stickerLibrary.length),58);
 await page.locator('#file').setInputFiles('logo_app.png');
 await page.waitForFunction(()=>document.getElementById('status').textContent.startsWith('Image loaded'),null,{timeout:15000});
 await page.waitForFunction(()=>mainLabelEnabledV78 && mainLabelExistsV77 && namePreview.style.display!=='none');
 await page.evaluate(()=>{toggleMainLabelV78(null,true);const el=document.getElementById('label');el.value='BROWSER TEST';el.dispatchEvent(new Event('input',{bubbles:true}));});
 // Retain shape-editing and sticker layers from the reference editor.
 await page.evaluate(()=>{setBgShape('circle'); if(bgBoxAutoFitEnabled)toggleBgAutoFit(); bgBoxRot=17; bgBoxW=.8; syncBgBox(); addStickerInstance(0);});
 await page.waitForFunction(()=>stickerInstances.length===1&&stickerInstances[0].loaded);
 await page.locator('#saveTopBtn').click();
 const pngPromise=page.waitForEvent('download');
 await page.locator('#saveButton').click();
 const png=await pngPromise;
 fs.mkdirSync('test-results',{recursive:true});
 await png.saveAs('test-results/transparent.png');
 assert.strictEqual(png.suggestedFilename(),'BROWSER TEST.png');
 await page.waitForFunction(()=>document.getElementById('status').textContent.startsWith('Saved:'));
 const saved=await page.evaluate(async()=>await (await BrowserApp.api('/projects')).json());
 assert.strictEqual(saved.projects.length,1);
 assert.strictEqual(saved.projects[0].name,'BROWSER TEST');
 // v129: recovery snapshots are created without manual saving or downloads.
 await page.evaluate(()=>BrowserApp.markDirty());
 await page.waitForFunction(async()=>{
   const db=await new Promise((resolve,reject)=>{const req=indexedDB.open('delta-green-evidence-maker');req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);});
   const project=await new Promise(resolve=>{const req=db.transaction('recovery').objectStore('recovery').get('current');req.onsuccess=()=>resolve(req.result);});
   db.close();
   return project?.project?.label==='BROWSER TEST';
 },null,{timeout:20000});

 const exportPromise=page.waitForEvent('download');
 await page.getByRole('button',{name:'Export Project',exact:true}).click();
 await (await exportPromise).saveAs('test-results/project.evidence.json');
 const project=JSON.parse(fs.readFileSync('test-results/project.evidence.json'));
 assert(project.sourceDataUrl.startsWith('data:image/png'));
 assert.strictEqual(project.stickers.length,1);
 assert(project.browserFonts.length>0);
 await page.reload();
 await page.waitForFunction(()=>document.getElementById('status').textContent==='Ready');
 await page.locator('#projectsTopBtn').click();
 await page.locator('.projectCard').click();
 console.log('REOPEN clicked', await page.evaluate(() => ({status:document.getElementById('status').textContent, projectsOpen:projectsPopoverOpen, count:document.querySelectorAll('.projectCard').length})));
 try {
 await page.waitForFunction(()=>{const s=document.getElementById('status').textContent;return s.startsWith('Project loaded:')||s.startsWith('ERROR:');},{timeout:12000});
 } catch(e) {
 console.error('REOPEN DIAGNOSTICS', JSON.stringify(await page.evaluate(async()=>({status:document.getElementById('status').textContent,projectsOpen:projectsPopoverOpen,subjectComplete:subject.complete,subjectWidth:subject.naturalWidth,imageLoaded,label:document.getElementById('label').value,stickers:stickerInstances.length,resourcesReady:true}))).slice(0,800));
 console.error('BROWSER ERRORS',errors,'FAILED RESPONSES',failed);
 throw e;
 }
 assert((await page.locator('#status').textContent()).startsWith('Project loaded:'), 'Saved project reopen failed: '+await page.locator('#status').textContent());
 assert.strictEqual(await page.locator('#label').inputValue(),'BROWSER TEST');
 assert.strictEqual(await page.evaluate(()=>bgBoxShape),'circle');
 assert.strictEqual(await page.evaluate(()=>bgBoxRot),project.bgBoxRot, 'Project rotation must match the exported project state');
 await page.waitForFunction(()=>stickerInstances[0]?.loaded);
 // Save conflict and versioning.
 await page.locator('#saveTopBtn').click();
 await page.locator('#saveButton').click();
 await page.waitForSelector('#saveConflictModal.show');
 const versionPromise=page.waitForEvent('download');
 await page.evaluate(()=>resolveSaveConflict('version'));
 const version=await versionPromise;
 assert.strictEqual(version.suggestedFilename(),'BROWSER TEST v2.png');
 await page.waitForFunction(()=>document.getElementById('status').textContent.startsWith('Saved:'));
 // Opaque export.
 await page.evaluate(()=>{const el=document.getElementById('label');el.value='OPAQUE TEST';el.dispatchEvent(new Event('input',{bubbles:true}));});
 await page.locator('#saveTopBtn').click();
 await page.locator('#transparent').uncheck();
 const opaquePromise=page.waitForEvent('download');
 await page.locator('#saveButton').click();
 await (await opaquePromise).saveAs('test-results/opaque.png');
 await page.screenshot({path:'test-results/editor.png',fullPage:true});
 // A different browser profile can restore the portable file.
 const fresh=await browser.newContext({viewport:{width:1600,height:1000},acceptDownloads:true});
 const other=await fresh.newPage();
 other.on('pageerror',e=>errors.push(e.message));
 await other.goto(process.env.EVIDENCE_TEST_URL || 'http://127.0.0.1:8765/');
 await other.waitForFunction(()=>document.getElementById('status').textContent==='Ready');
 await other.locator('#projectsTopBtn').click();
 const picker=other.waitForEvent('filechooser');
 await other.getByRole('button',{name:'Import Project',exact:true}).click();
 await (await picker).setFiles('test-results/project.evidence.json');
 await other.waitForFunction(()=>document.getElementById('status').textContent.startsWith('Project imported:'));
 assert.strictEqual(await other.locator('#label').inputValue(),'BROWSER TEST');
 await other.waitForFunction(()=>stickerInstances[0]?.loaded);
 assert.strictEqual(await other.evaluate(()=>bgBoxShape),'circle');
 assert.strictEqual(await other.evaluate(()=>imageLoaded),true);
 // Reject unusable desktop references with an actionable message.
 const bad=await other.evaluate(async()=>{
  try{await BrowserApp.restoreResources({type:'evidence-photo-project',sourceRef:'SOURCES/missing.png'});return '';}
  catch(e){return e.message;}
 });
 assert(bad.includes('Import Desktop Folder'));
 assert.deepStrictEqual(errors,[]);
 assert.deepStrictEqual(failed,[]);
 console.log('PASS: startup, 44 frames, 58 stickers, upload, shape/sticker editing, PNG export, persistence/reopen, conflict/version, opaque export, portable project import, invalid desktop source error.');
 clearTimeout(deadline);
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
