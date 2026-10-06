/* Browser storage and file adapter for the v42 editor. No server or Python required. */
'use strict';
window.BrowserApp = (() => {
  const nativeFetch = window.fetch.bind(window);
  const base = new URL('.', document.currentScript.src);
  const thumbnails = new Map();
  let manifest, db, catalogPromise, outputDirectory = null;
  let fontList = [], assets = {frames: [], stickers: []};
  const respond = (data, status = 200) => new Response(JSON.stringify(data), {
    status, headers: {'Content-Type': 'application/json'}
  });
  const message = text => {
    const node = document.getElementById('status');
    if (node) node.textContent = text;
  };
  const absolute = path => new URL(path, base).href;
  const safeName = value => String(value || 'UNKNOWN').replace(/[<>:"/\\|?*\x00-\x1f]/g, '')
    .replace(/[. ]+$/g, '').trim().slice(0, 180) || 'UNKNOWN';
  const readData = blob => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = () => reject(new Error('Could not read the selected file.'));
    reader.readAsDataURL(blob);
  });
  const loadImage = src => new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('That image could not be decoded.'));
    image.src = src;
  });
  const canvasBlob = canvas => new Promise((resolve, reject) =>
    canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('PNG export failed.')), 'image/png'));
  function openDatabase() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open('delta-green-evidence-maker', 1);
      request.onupgradeneeded = () => {
        for (const name of ['projects', 'fonts', 'assets', 'settings', 'exports']) {
          request.result.createObjectStore(name, {keyPath: 'id'});
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(new Error('Browser storage is unavailable. Allow site storage and reload.'));
      request.onblocked = () => reject(new Error('Close other Evidence Maker tabs and reload.'));
    });
  }
  function read(store, id) {
    return new Promise((resolve, reject) => {
      const tx = db.transaction(store);
      const request = id === undefined ? tx.objectStore(store).getAll() : tx.objectStore(store).get(id);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }
  function write(store, value) {
    return new Promise((resolve, reject) => {
      const tx = db.transaction(store, 'readwrite');
      tx.objectStore(store).put(value);
      tx.oncomplete = resolve;
      tx.onerror = tx.onabort = () => reject(new Error('Could not save browser data. Storage may be full; export a project backup.'));
    });
  }
  async function reloadResources() {
    fontList = [...manifest.fonts, ...await read('fonts')];
    const custom = await read('assets');
    assets.frames = custom.filter(item => item.kind === 'frames');
    assets.stickers = custom.filter(item => item.kind === 'stickers');
  }
  const ready = (async () => {
    const response = await nativeFetch(absolute('manifest.json'));
    if (!response.ok) throw new Error('The asset library could not be loaded. Refresh this page.');
    manifest = await response.json();
    db = await openDatabase();
    await reloadResources();
  })();
  // init() reports startup errors; keep the eagerly started promise handled.
  ready.catch(error => message(error.message));

  function asset(kind, file) {
    const custom = assets[kind].find(item => item.file === file);
    return custom ? custom.src : absolute(kind + '/' + String(file).split('/').map(encodeURIComponent).join('/'));
  }
  function fontUrl(id) {
    const font = fontList.find(item => item.id === id) || fontList[0];
    return font ? font.dataUrl || absolute(font.url) : '';
  }
  function library(kind) {
    const bundled = manifest[kind];
    return {
      ...bundled,
      [kind]: [...bundled[kind], ...assets[kind]],
      categories: [...bundled.categories, ...(assets[kind].length ? [{name:'Imported', subcategories:[]}] : [])]
    };
  }
  async function imageUpload(blob, name) {
    if (!(blob instanceof Blob)) throw new Error('Choose an image first.');
    const preview = await readData(blob);
    const image = await loadImage(preview);
    return {ok:true, preview, name: name || blob.name || 'image.png', width:image.naturalWidth, height:image.naturalHeight};
  }
  function download(blob, name) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = name;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }
  async function outputExists(name) {
    if (outputDirectory) {
      try { await outputDirectory.getFileHandle(name); return true; }
      catch (error) { if (error.name !== 'NotFoundError') throw error; }
      return false;
    }
    return !!await read('exports', name);
  }
  async function saveComposite(fd) {
    const original = fd.get('file');
    if (!(original instanceof Blob)) throw new Error('The composed PNG is missing.');
    let stem = safeName(fd.get('autoName') === 'true' ? fd.get('label') : String(fd.get('fileName') || 'UNKNOWN').replace(/\.png$/i, ''));
    let filename = stem + '.png';
    const mode = fd.get('saveMode') || 'ask';
    const saveProject = fd.get('saveRawProject') === 'true';
    let project = null;
    // Parse and validate before downloading anything.
    if (saveProject) {
      const raw = fd.get('projectData');
      project = JSON.parse(raw instanceof Blob ? await raw.text() : String(raw));
      validateProject(project);
    }
    const imageExists = await outputExists(filename);
    const projectExists = saveProject && !!await read('projects', stem);
    if (mode === 'ask' && (imageExists || projectExists)) {
      return respond({ok:false, conflict:true, filename, image_exists:imageExists, project_exists:projectExists}, 409);
    }
    if (mode === 'version' && (imageExists || projectExists)) {
      const baseStem = stem.replace(/ v\d+$/i, '');
      let version = 2;
      while (await outputExists(baseStem + ' v' + version + '.png') ||
        (saveProject && await read('projects', baseStem + ' v' + version))) version++;
      stem = baseStem + ' v' + version;
      filename = stem + '.png';
    }
    let blob = original;
    const src = await readData(original);
    const image = await loadImage(src);
    if (fd.get('transparent') !== 'true') {
      const canvas = document.createElement('canvas');
      canvas.width = image.naturalWidth;
      canvas.height = image.naturalHeight;
      const ctx = canvas.getContext('2d');
      ctx.fillStyle = '#16191b';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(image, 0, 0);
      blob = await canvasBlob(canvas);
    }
    const thumb = document.createElement('canvas');
    const scale = Math.min(1, 240 / Math.max(image.naturalWidth, image.naturalHeight));
    thumb.width = Math.max(1, Math.round(image.naturalWidth * scale));
    thumb.height = Math.max(1, Math.round(image.naturalHeight * scale));
    thumb.getContext('2d').drawImage(image, 0, 0, thumb.width, thumb.height);
    if (project) {
      project.projectName = stem;
      project.savedPngName = filename;
      project.savedAt = new Date().toISOString();
      project.savedWith = 'Evidence Maker v43 Browser';
      await write('projects', {id:stem, project, thumbnail:thumb.toDataURL('image/png')});
    }
    if (outputDirectory) {
      const file = await outputDirectory.getFileHandle(filename, {create:true});
      const stream = await file.createWritable();
      try { await stream.write(blob); await stream.close(); }
      catch (error) { try { await stream.abort(); } catch (_) {} throw error; }
    } else {
      download(blob, filename);
    }
    await write('exports', {id:filename, time:Date.now()});
    return respond({ok:true, filename, saved_to:outputDirectory ? outputDirectory.name + '/' + filename : 'Downloads/' + filename,
      raw_project_saved_to:project ? 'this browser' : null});
  }
  function validateProject(project) {
    if (!project || project.type !== 'evidence-photo-project' || typeof project !== 'object') {
      throw new Error('This is not an Evidence Maker project.');
    }
    if (project.sourceRef && !project.sourceDataUrl) {
      throw new Error('This desktop project references a separate source image. Use Import Desktop Folder and select its RAW PROJECTS folder.');
    }
    // Imported files must not turn into network requests or executable URLs.
    const checkImage = value => { if (value && !/^data:image\/(png|jpeg|webp|gif|bmp);base64,/i.test(value)) throw new Error('Project contains an unsupported image reference.'); };
    checkImage(project.sourceDataUrl);
    checkImage(project.bgBackgroundImageDataUrl);
    for (const item of project.stickers || []) if (item.custom) checkImage(item.src);
    for (const item of project.browserAssets || []) checkImage(item.src);
    for (const font of project.browserFonts || []) {
      if (!/^[a-zA-Z0-9_-]+$/.test(font.id) || !/^data:[a-zA-Z0-9/+.\-]*;base64,[a-zA-Z0-9+/=]+$/.test(font.dataUrl || '')) {
        throw new Error('Project contains an invalid font.');
      }
    }
    for (const item of [project.onlineItem, ...(project.extras || []).map(x => x.onlineItem)].filter(Boolean)) {
      if (!/^[a-z0-9-]+$/.test(item.id)) throw new Error('Project contains an invalid online font.');
    }
  }
  async function packProject(project) {
    await ready;
    const ids = new Set([project.fontId, ...(project.extras || []).filter(x=>x.enabled).map(x=>x.fontId)]);
    project.browserFonts = await Promise.all(fontList.filter(f => ids.has(f.id)).map(async font => ({
      id:font.id, name:font.name, custom:true, themed:font.themed,
      dataUrl:font.dataUrl || await readData(await (await nativeFetch(fontUrl(font.id))).blob())
    })));
    const frame = assets.frames.find(item => item.id === project.frameId);
    const stickerFiles = new Set((project.stickers || []).map(item => item.file));
    project.browserAssets = [...(frame ? [frame] : []), ...assets.stickers.filter(item => stickerFiles.has(item.file))];
    project.savedWith = 'Evidence Maker v43 Browser';
    return project;
  }
  async function restoreResources(project) {
    await ready;
    validateProject(project);
    for (const item of project.browserFonts || []) await write('fonts', item);
    for (const item of project.browserAssets || []) {
      if (!['frames','stickers'].includes(item.kind)) throw new Error('Invalid project asset.');
      await write('assets', item);
    }
    await reloadResources();
    if (typeof loadFrames === 'function') await loadFrames(true);
  }
  async function getCatalog() {
    if (!catalogPromise) {
      catalogPromise = nativeFetch('https://api.fontsource.org/v1/fonts')
        .then(r => {if (!r.ok) throw new Error('Online font catalog is unavailable.'); return r.json();})
        .then(list => list.filter(f => f.family && f.id && f.type !== 'icons').sort((a,b)=>a.family.localeCompare(b.family)))
        .catch(error => {catalogPromise=null; throw error;});
    }
    return catalogPromise;
  }
  function fontItem(font) {
    const first = (list, preferred) => (list || []).includes(preferred) ? preferred : (list || [preferred])[0];
    return {id:font.id, family:font.family, weight:first(font.weights,400),
      style:first(font.styles,'normal'), subset:font.defSubset || first(font.subsets,'latin'),
      category:font.category, installed:fontList.some(f=>f.name.toLowerCase()===font.family.toLowerCase())};
  }
  async function onlineFonts(url) {
    const all = await getCatalog(), query=(url.searchParams.get('q') || '').toLowerCase();
    const category=url.searchParams.get('category') || 'horror';
    let matches;
    if (query) matches=all.filter(f=>(f.family+' '+f.id).toLowerCase().includes(query));
    else if (category === 'all') matches=all;
    else if (manifest.categories[category]) matches=all.filter(f=>f.category===manifest.categories[category]);
    else {
      const seeds=manifest.styles[category] || [], fallbacks=manifest.fallbacks[category] || ['display'];
      matches=[...seeds.map(id=>all.find(f=>f.id===id)).filter(Boolean),
        ...all.filter(f=>!seeds.includes(f.id)&&fallbacks.includes(f.category))];
    }
    const page=Math.max(1,Number(url.searchParams.get('page')) || 1), size=96;
    return {ok:true, items:matches.slice((page-1)*size,page*size).map(fontItem), total:matches.length, page, has_more:page*size<matches.length};
  }
  async function addFont(blob, name, id) {
    const dataUrl = await readData(blob);
    if (!id) {
      const digest=await crypto.subtle.digest('SHA-256',await blob.arrayBuffer());
      id='custom_'+Array.from(new Uint8Array(digest)).map(x=>x.toString(16).padStart(2,'0')).join('').slice(0,16);
    }
    const face = await new FontFace('verify_'+id, await blob.arrayBuffer()).load();
    if (face.status !== 'loaded') throw new Error('The font could not be loaded.');
    await write('fonts', {id,name,custom:true,themed:true,dataUrl});
    await reloadResources();
    return {id,name};
  }
  async function unzipFonts(file) {
    const buffer=await file.arrayBuffer(), view=new DataView(buffer), bytes=new Uint8Array(buffer);
    let end=bytes.length-22;
    while(end>=Math.max(0,bytes.length-65557) && view.getUint32(end,true)!==0x06054b50) end--;
    if(end<Math.max(0,bytes.length-65557)) throw new Error('Invalid ZIP archive.');
    const count=view.getUint16(end+10,true);
    let pos=view.getUint32(end+16,true), total=0;
    const output=[];
    for(let i=0;i<count;i++){
      if(view.getUint32(pos,true)!==0x02014b50) throw new Error('Invalid ZIP directory.');
      const method=view.getUint16(pos+10,true), packed=view.getUint32(pos+20,true), size=view.getUint32(pos+24,true);
      const nameLength=view.getUint16(pos+28,true), extra=view.getUint16(pos+30,true), comment=view.getUint16(pos+32,true);
      const name=new TextDecoder().decode(bytes.slice(pos+46,pos+46+nameLength));
      const offset=view.getUint32(pos+42,true);
      pos+=46+nameLength+extra+comment;
      if(!/\.(ttf|otf|woff2?|ttc)$/i.test(name) || name.startsWith('__MACOSX/')) continue;
      total+=size;
      if(total>50*1024*1024 || output.length>=100) throw new Error('Font ZIP is too large.');
      if(view.getUint32(offset,true)!==0x04034b50) throw new Error('Invalid ZIP entry.');
      const start=offset+30+view.getUint16(offset+26,true)+view.getUint16(offset+28,true);
      let blob=new Blob([bytes.slice(start,start+packed)]);
      if(method===8) blob=await new Response(blob.stream().pipeThrough(new DecompressionStream('deflate-raw'))).blob();
      else if(method!==0) throw new Error('Unsupported ZIP compression.');
      if(blob.size!==size) throw new Error('Damaged font ZIP entry.');
      output.push({blob,name:name.split('/').pop()});
    }
    return output;
  }
  async function api(path, options={}) {
    try {
      await ready;
      const url=new URL(path,'https://local.invalid');
      const route=url.pathname, body=options.body;
      if(route==='/frames') return respond(library('frames'));
      if(route==='/stickers') return respond(library('stickers'));
      if(route==='/fonts' || route==='/fonts/refresh') {await reloadResources();return respond(fontList);}
      if(route==='/upload') return respond(await imageUpload(body.get('file')));
      if(route==='/from-url') {
        const input=JSON.parse(body).url, remote=new URL(input);
        if(!['https:','http:'].includes(remote.protocol)) throw new Error('Use a full HTTPS image URL.');
        let response;
        try {response=await nativeFetch(remote.href,{mode:'cors',credentials:'omit'});}
        catch (_) {throw new Error('This image host blocks browser access. Download the image and use Upload instead.');}
        if(!response.ok) throw new Error('The image host returned '+response.status+'. Download it and use Upload instead.');
        return respond(await imageUpload(await response.blob(),remote.pathname.split('/').pop()));
      }
      if(route==='/clear-source') return respond({ok:true});
      if(route==='/settings' || route==='/settings/update') {
        let settings=await read('settings','preferences') || {id:'preferences',preview_background:'dark'};
        if(route.endsWith('/update')) {
          const value=JSON.parse(body).preview_background;
          if(['dark','check','white'].includes(value)) settings.preview_background=value;
          await write('settings',settings);
        }
        return respond({ok:true,...settings,save_folder:outputDirectory?outputDirectory.name:'Browser Downloads'});
      }
      if(route==='/save-composite') return await saveComposite(body);
      if(route==='/projects') {
        const records=await read('projects');
        records.sort((a,b)=>(b.project.savedAt||'').localeCompare(a.project.savedAt||''));
        for(const item of records) thumbnails.set(item.id,item.thumbnail);
        return respond({ok:true,folder:'Saved in this browser • Export Project for a backup',projects:records.map(item=>({
          id:item.id,name:item.project.projectName||item.id,label:item.project.label,
          saved_at:item.project.savedAt,has_thumbnail:!!item.thumbnail,saved_png:item.project.savedPngName
        }))});
      }
      if(route.startsWith('/project-data/')) {
        const item=await read('projects',decodeURIComponent(route.slice('/project-data/'.length)));
        if(!item) throw new Error('This project is no longer in browser storage.');
        return respond({ok:true,project:item.project});
      }
      if(route==='/online-fonts') return respond(await onlineFonts(url));
      if(route==='/online-font/install') {
        const id=JSON.parse(body).id;
        if(!/^[a-z0-9-]+$/.test(id)) throw new Error('Invalid online font.');
        const font=(await getCatalog()).find(f=>f.id===id);
        if(!font) throw new Error('Online font was not found.');
        const item=fontItem(font);
        const response=await nativeFetch('https://cdn.jsdelivr.net/fontsource/fonts/'+id+'@latest/'+item.subset+'-'+item.weight+'-'+item.style+'.woff2');
        if(!response.ok) throw new Error('Could not download that font.');
        await addFont(await response.blob(),font.family,'online_'+id);
        return respond({ok:true,family:font.family});
      }
      if(route==='/font-import') {
        const file=body.get('file');
        if(!file) throw new Error('Choose a font file.');
        const list=/\.zip$/i.test(file.name) ? await unzipFonts(file) : [{blob:file,name:file.name}];
        if(!list.length) throw new Error('No supported fonts found in that ZIP.');
        for(const entry of list) await addFont(entry.blob,entry.name.replace(/\.[^.]+$/,'').replaceAll('_',' '));
        return respond({ok:true,count:list.length});
      }
      throw new Error('This desktop-only action is unavailable in the browser edition.');
    } catch(error) {
      console.warn('Evidence Maker:',error.message);
      return respond({ok:false,error:error.message},400);
    }
  }
  function selectFiles({accept='',multiple=false,directory=false}, action) {
    const input=document.createElement('input');
    input.type='file';input.accept=accept;input.multiple=multiple;
    if(directory) input.webkitdirectory=true;
    input.hidden=true;document.body.appendChild(input);
    input.onchange=async()=>{try{await ready;await action(Array.from(input.files));}catch(error){message('ERROR: '+error.message);}finally{input.remove();}};
    input.oncancel=()=>input.remove();
    input.click();
  }
  async function exportProjectFile() {
    try {
      await ready;
      if(!imageLoaded) throw new Error('Add an image first.');
      await ensurePreviewFontReadyForSave();
      const project=await packProject(await exportProjectState());
      download(new Blob([JSON.stringify(project)],{type:'application/json'}),safeName(project.label)+'.evidence.json');
      message('Project backup downloaded. Keep this file to reopen your work on another device.');
    } catch(error) {message('ERROR: '+error.message);}
  }
  async function importProject(project, name) {
    validateProject(project);
    await importProjectState(project);
    const id=safeName(project.projectName||project.label||name);
    project.projectName=id;
    project.savedAt=new Date().toISOString();
    // Import never overwrites a different saved project without choosing a new name.
    let finalId=id, version=2;
    while(await read('projects',finalId)) finalId=id+' imported '+version++;
    project.projectName=finalId;
    await write('projects',{id:finalId,project,thumbnail:''});
    hideProjectsPopover();
    message('Project imported: '+finalId);
  }
  function importProjectFiles() {
    selectFiles({accept:'.json'},async files=>{
      if(!files.length)return;
      await importProject(JSON.parse(await files[0].text()),files[0].name);
    });
  }
  function importDesktopFolder() {
    selectFiles({directory:true,multiple:true},async files=>{
      const projects=files.filter(f=>f.name==='project.json');
      if(!projects.length)throw new Error('Select RAW PROJECTS or a folder containing project.json.');
      for(const file of projects){
        const project=JSON.parse(await file.text());
        if(project.sourceRef&&!project.sourceDataUrl){
          const filename=String(project.sourceRef).replaceAll('\\','/').split('/').pop();
          const image=files.find(f=>f.name===filename);
          if(!image)throw new Error('Missing source image '+filename+'. Select the full RAW PROJECTS folder.');
          project.sourceDataUrl=await readData(image);
        }
        await importProject(project,file.webkitRelativePath);
      }
      message('Imported '+projects.length+' desktop project(s). Last imported project is open.');
    });
  }
  function importAssets(kind) {
    selectFiles({accept:'image/png,image/jpeg,image/webp',multiple:true},async files=>{
      for(const file of files){
        const preview=await imageUpload(file);
        const id='import_'+crypto.randomUUID();
        const item={id,kind,file:id,name:file.name.replace(/\.[^.]+$/,''),category:'Imported',subcategory:'',src:preview.preview};
        if(kind==='frames'){
          const w=preview.width,h=preview.height;
          Object.assign(item,{photo:[Math.round(w*.14),Math.round(h*.16),Math.round(w*.88),Math.round(h*.74)],labelDefault:[.5,.88]});
        }
        await write('assets',item);
      }
      await reloadResources();
      if(kind==='frames') await loadFrames(true);else await loadStickers();
      message('Imported '+files.length+' '+kind+'.'+(kind==='frames'?' Adjust the image window to fit your custom frame.':''));
    });
  }
  async function chooseDirectory() {
    if(!window.showDirectoryPicker){
      message('This browser uses Downloads. Choose the download location in your browser settings.');
      return;
    }
    try {
      outputDirectory=await window.showDirectoryPicker({mode:'readwrite'});
      document.getElementById('savePath').value=outputDirectory.name;
      message('PNGs will save to '+outputDirectory.name+' for this session.');
    } catch(error) {if(error.name!=='AbortError')message('Could not use that folder: '+error.message);}
  }
  function installUI() {
    const footer=document.querySelector('.projectPopoverFooter');
    if(footer){
      const button=document.createElement('button');button.className='smallBtn';
      button.textContent='Import Desktop Folder';button.onclick=importDesktopFolder;
      footer.appendChild(button);
    }
    const help=document.querySelector('#helpModal .modalBox');
    if(help){
      const note=document.createElement('p');
      note.textContent='Browser edition: saved projects live on this device. Export Project downloads a self-contained backup. Import Project reopens it. Import Desktop Folder reads v42 RAW PROJECTS, including its SOURCES folder. PNGs download normally, or use Choose Folder in supporting browsers. Some image hosts block direct URL loading; upload the downloaded file instead.';
      help.appendChild(note);
    }
    const conflict=document.getElementById('saveConflictModal');
    if(conflict){
      const note=document.createElement('p');note.style.cssText='font-size:11px;color:#aebbc1';
      note.textContent='In Downloads mode, Replace updates the browser project and starts another download; the browser may add a number to the PNG filename.';
      conflict.querySelector('.conflictBox').appendChild(note);
    }
  }
  return {api,ready,asset,fontUrl,thumbnail:id=>thumbnails.get(id)||'',packProject,restoreResources,
    exportProjectFile,importProjectFiles,importDesktopFolder,importAssets,chooseDirectory,installUI};
})();
