const $ = id => document.getElementById(id);
const state = {overview:null,process:'sky130',run:null,report:null,view:'overview',waveKind:'schematic',wave:null,layout:null,layers:new Set(),doc:null,experiment:null,plot:null,layoutZoom:1,layoutPan:[0,0],drag:null,drc:null,drcLayout:null,drcFocus:null,lvs:null,pex:null,schematic:null,schematicView:'functional',editorExperiment:null};

async function api(path, options={}) {
  const response = await fetch(path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}
const query = (path, fields) => `${path}?${new URLSearchParams(fields)}`;
function notice(message, error=false) { const el=$('notice'); el.textContent=message; el.classList.toggle('error',error); el.hidden=false; clearTimeout(notice.timer); notice.timer=setTimeout(()=>el.hidden=true,8500); }
function clear(node){node.replaceChildren();}
function add(parent,tag,text,className){const el=document.createElement(tag); if(text!==undefined)el.textContent=String(text); if(className)el.className=className; parent.append(el);return el;}
function fmtPs(value){return Number.isFinite(value)?`${(value*1e12).toFixed(2)} ps`:'—';}
function metric(checks,kind){return kind==='schematic'?(checks.baseline||checks.schematic_simulation):(checks.capacitance_extracted||checks.capacitance_extracted_simulation);}
function drcValue(){const c=state.report?.checks||{};return state.process==='sky130'?c.native_klayout_drc_items:c.native_klayout_connected_full_drc_items;}
function magicValue(){const c=state.report?.checks||{};return state.process==='sky130'?c.magic_full_drc_errors:c.magic_connected_drc_errors;}
function lvsValue(){const c=state.report?.checks||{};return state.process==='sky130'?c.lvs:c.connected_lvs;}
function selectRun(){const options=state.overview.runs[state.process]||[];const select=$('run-select');clear(select);for(const item of options){const opt=add(select,'option',`${item.status.toUpperCase()} · ${item.id.slice(0,8)}`);opt.value=item.id;}const chosen=options.find(item=>item.status==='passed')||options[0];state.run=chosen?.id||null;select.value=state.run||'';}
async function loadRun(){if(!state.run){state.report=null;notice('No validation runs found for this process.',true);return;}state.report=await api(query('/api/run',{process:state.process,run:state.run}));state.wave=null;state.layout=null;state.drc=null;state.drcLayout=null;state.lvs=null;state.pex=null;state.schematic=null;state.editorExperiment=null;state.layers.clear();renderOverview();renderSchematic();renderVerification();configureEvidenceSelectors();if(state.view==='waveforms')await loadWave();if(state.view==='layout')await loadLayout();if(state.view==='verification')await loadEvidence();if(state.view==='pex')await loadPex();if(state.view==='schematic')await loadSchematic();}
function row(parent,label,value,cls=''){const div=add(parent,'div',undefined,'pipeline-item');add(div,'strong',label);add(div,'span',value,cls);}
function renderOverview(){const report=state.report;if(!report)return;const c=report.checks||{},spec=state.overview.processes[state.process],sch=metric(c,'schematic')||{},pex=metric(c,'postlayout')||{};const host=report.host?.system==='Darwin'?`Mac ${report.host?.arch||'?'}`:report.host?.system?`${report.host.system} ${report.host?.arch||''} host`:'host unrecorded';$('hero-process').textContent=spec.title;$('hero-subtitle').textContent=`${spec.voltage} V · ${spec.pdk} · ${host}`;$('hero-corner').textContent=spec.corner;$('hero-status').textContent=report.status.toUpperCase();$('hero-status').className='hero-value '+(report.status==='passed'?'check-good':'check-warn');$('hero-run').textContent=state.run;$('hero-drc').textContent=drcValue()===0?'0 DRC items':`${drcValue()??'—'} DRC items`;$('hero-lvs').textContent=lvsValue()||'LVS unavailable';
  const grid=$('metric-grid');clear(grid);for(const [label,val,sub] of [['Schematic tPHL',fmtPs(sch.tphl),'50% input → output'],['Schematic tPLH',fmtPs(sch.tplh),'50% input → output'],['Extracted tPHL',fmtPs(pex.tphl),`Δ ${fmtPs(pex.tphl-sch.tphl)}`],['Extracted tPLH',fmtPs(pex.tplh),`Δ ${fmtPs(pex.tplh-sch.tplh)}`]]){const card=add(grid,'div',undefined,'metric-card');add(card,'div',label,'label');add(card,'div',val,'value');add(card,'div',sub,'sub');}
  const pipeline=$('pipeline');clear(pipeline);row(pipeline,'Schematic simulation',sch.tphl?'Measured':'Missing',sch.tphl?'check-good':'check-warn');row(pipeline,'Connected layout',report.status==='passed'?'GDS generated':'Inspect run',report.status==='passed'?'check-good':'check-warn');row(pipeline,'Magic DRC',magicValue()===0?'0 errors':`${magicValue()??'—'} errors`,magicValue()===0?'check-good':'check-warn');row(pipeline,'Native KLayout DRC',drcValue()===0?'0 items':`${drcValue()??'—'} items`,drcValue()===0?'check-good':'check-warn');row(pipeline,'Netgen LVS',lvsValue()?.includes('unique match')?'Unique match':'Inspect run',lvsValue()?.includes('unique match')?'check-good':'check-warn');row(pipeline,'Capacitance PEX',pex.tphl?'Measured':'Missing',pex.tphl?'check-good':'check-warn');
  const interpretation=$('interpretation');clear(interpretation);const items=[report.scope||'Open PDK lab check',...(report.unresolved||[])];if(state.process==='sky130')items.push('Antenna and density were not checked; distributed wire resistance and foundry qualification remain open.');items.push('R2 provides storage. Remote compute has not been configured.');for(const item of items)add(interpretation,'div',item,'interpretation-item');
}
function renderSchematic(){const report=state.report;if(!report)return;const spec=state.overview.processes[state.process],list=$('device-params');clear(list);for(const [label,value] of [['Process',spec.title],['Supply',`${spec.voltage} V`],['Corner',spec.corner],['NMOS',`${spec.n_width} × ${spec.channel}`],['PMOS',`${spec.p_width} × ${spec.channel}`],['Output load','5 fF']]){const item=add(list,'div',undefined,'parameter-row');add(item,'span',label);add(item,'span',value);}const name='inverter.spice';if(report.artifacts?.includes(name))api(query('/api/artifact',{process:state.process,run:state.run,name})).then(data=>$('schematic-code').textContent=data.text).catch(err=>$('schematic-code').textContent=err.message);else $('schematic-code').textContent='Reference netlist is absent from this run manifest.';}
function renderVerification(){const report=state.report;if(!report)return;const c=report.checks||{},cards=$('verification-cards');clear(cards);for(const [title,value,sub,cls] of [['Magic DRC',`${magicValue()??'—'} errors`,'Worker layout check',magicValue()===0?'check-good':'check-warn'],['Native KLayout',`${drcValue()??'—'} items`,'Full vendor rule deck on Mac',drcValue()===0?'check-good':'check-warn'],['Netgen LVS',lvsValue()?.includes('unique match')?'UNIQUE MATCH':'INSPECT','2 devices · 4 nets',lvsValue()?.includes('unique match')?'check-good':'check-warn']]){const card=add(cards,'div',undefined,'verification-card');add(card,'div',title,'title');add(card,'div',value,`value ${cls}`);add(card,'div',sub,'sub');}
  const checks=$('checks-table');clear(checks);const entries=state.process==='sky130'?[['Connected Magic DRC',c.magic_full_drc_errors===0?'0 errors':'Inspect'],['Connected KLayout DRC',c.native_klayout_drc_items===0?'0 items':'Inspect'],['Negative DRC control',`${c.negative_drc_errors??'—'} error detected`],['Negative LVS control',c.negative_lvs||'—'],['GDS export feedback',String(c.gds_export_feedback??'—')]]:[['Connected Magic DRC',c.magic_connected_drc_errors===0?'0 errors':'Inspect'],['Connected KLayout DRC',c.native_klayout_connected_full_drc_items===0?'0 items':'Inspect'],['Default PCell Magic DRC',`${c.magic_default_pcell_drc_errors??'—'} errors`],['Default PCell KLayout metal1',`${c.native_klayout_default_pcell_metal1_items??'—'} items`],['Disconnected probe LVS',c.probe_lvs||'—'],['Wrong-bulk LVS control',c.negative_lvs||'—']];for(const [label,value] of entries){const item=add(checks,'div',undefined,'check-row');add(item,'span',label);add(item,'strong',value,value==='0 errors'||value==='0 items'?'check-good':value.includes('mismatch')||value.includes('rejected')||value.includes('detected')?'check-warn':'');}
  const limits=$('unresolved-list');clear(limits);for(const item of report.unresolved||['No antenna or density signoff','No distributed wire resistance in extraction','No foundry qualification or silicon measurement'])add(limits,'div',item,'interpretation-item');const select=$('artifact-select');clear(select);for(const name of report.artifacts||[]){const opt=add(select,'option',name);opt.value=name;}if([...select.options].some(o=>o.value==='inverter.spice'))select.value='inverter.spice';$('artifact-content').textContent='Select an artifact to inspect its text.';}
function setView(view){state.view=view;for(const el of document.querySelectorAll('.view'))el.classList.toggle('active',el.id===`view-${view}`);for(const el of document.querySelectorAll('.nav-item'))el.classList.toggle('active',el.dataset.view===view);$('view-crumb').textContent=view.toUpperCase();if(view==='waveforms')loadWave().catch(err=>notice(err.message,true));if(view==='layout')loadLayout().catch(err=>notice(err.message,true));if(view==='verification')loadEvidence().catch(err=>notice(err.message,true));if(view==='pex')loadPex().catch(err=>notice(err.message,true));if(view==='schematic'){loadSchematic().catch(err=>notice(err.message,true));if(state.editorExperiment)requestAnimationFrame(()=>drawPlot($('schematic-canvas'),state.editorExperiment.samples));}if(view==='documents'&&!state.doc)loadDoc(state.overview.documents[0]).catch(err=>notice(err.message,true));if(view==='experiments'&&state.experiment)requestAnimationFrame(()=>drawPlot($('experiment-canvas'),state.experiment.samples));}
async function loadWave(){if(!state.report)return;$('wave-source').textContent='Generating trace from the selected run…';const kind=state.waveKind;const data=await api(query('/api/waveform',{process:state.process,run:state.run,kind}));if(kind!==state.waveKind)return;state.wave=data;$('wave-source').textContent=`${data.source} · ${data.samples.length.toLocaleString()} points · source ${data.run_id.slice(0,8)}`;requestAnimationFrame(()=>drawPlot($('wave-canvas'),data.samples));const stats=metric(state.report.checks,kind),box=$('wave-metrics');clear(box);for(const [label,value] of [['tPHL',fmtPs(stats?.tphl)],['tPLH',fmtPs(stats?.tplh)],['VOUT high',stats?.vout_high==null?'—':`${Number(stats.vout_high).toFixed(3)} V`],['VOUT low',stats?.vout_low==null?'—':`${Number(stats.vout_low).toExponential(2)} V`]]){const card=add(box,'div',undefined,'detail');add(card,'div',label,'label');add(card,'div',value,'value');}}
function canvasSetup(canvas){const rect=canvas.getBoundingClientRect(),dpr=window.devicePixelRatio||1;canvas.width=Math.max(1,Math.round(rect.width*dpr));canvas.height=Math.max(1,Math.round(rect.height*dpr));const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);return {ctx,w:rect.width,h:rect.height};}
function drawPlot(canvas,samples){if(!samples?.length)return;const {ctx,w,h}=canvasSetup(canvas),pad={l:54,r:24,t:22,b:38};ctx.clearRect(0,0,w,h);ctx.fillStyle='#0a1c27';ctx.fillRect(0,0,w,h);const x0=samples[0][0],x1=samples[samples.length-1][0],y1=Math.max(...samples.map(row=>Math.max(row[1],row[2])))*1.1||1;const x=v=>pad.l+(v-x0)/(x1-x0)*(w-pad.l-pad.r),y=v=>h-pad.b-v/y1*(h-pad.t-pad.b);ctx.strokeStyle='#254453';ctx.lineWidth=1;ctx.fillStyle='#83a1ae';ctx.font='11px ui-monospace, monospace';for(let i=0;i<=6;i++){const xx=pad.l+i*(w-pad.l-pad.r)/6;ctx.beginPath();ctx.moveTo(xx,pad.t);ctx.lineTo(xx,h-pad.b);ctx.stroke();ctx.fillText((x0+(x1-x0)*i/6).toFixed(1),xx-12,h-14);}for(let i=0;i<=4;i++){const yy=pad.t+i*(h-pad.t-pad.b)/4;ctx.beginPath();ctx.moveTo(pad.l,yy);ctx.lineTo(w-pad.r,yy);ctx.stroke();ctx.fillText((y1*(1-i/4)).toFixed(1),8,yy+4);}ctx.save();ctx.beginPath();ctx.rect(pad.l,pad.t,w-pad.l-pad.r,h-pad.t-pad.b);ctx.clip();for(const [col,color] of [[1,'#5ad9e9'],[2,'#f6b76a']]){ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();for(let i=0;i<samples.length;i++){const point=samples[i];if(i===0)ctx.moveTo(x(point[0]),y(point[col]));else ctx.lineTo(x(point[0]),y(point[col]));}ctx.stroke();}ctx.restore();canvas._plot={samples,pad,x0,x1,y1};}
function plotHover(event){const canvas=event.currentTarget,p=canvas._plot,tip=$('wave-tooltip');if(!p)return;const rect=canvas.getBoundingClientRect(),px=event.clientX-rect.left,time=p.x0+(px-p.pad.l)/(rect.width-p.pad.l-p.pad.r)*(p.x1-p.x0);if(px<p.pad.l||px>rect.width-p.pad.r){tip.hidden=true;return;}const index=Math.max(0,Math.min(p.samples.length-1,Math.round((time-p.x0)/(p.x1-p.x0)*(p.samples.length-1))));const row=p.samples[index];tip.textContent=`${row[0].toFixed(3)} ns\nIN   ${row[1].toFixed(3)} V\nOUT  ${row[2].toFixed(3)} V`;tip.style.left=`${Math.min(px+14,rect.width-130)}px`;tip.style.top=`${Math.max(12,event.clientY-rect.top-72)}px`;tip.hidden=false;}
async function loadLayout(){if(!state.report)return;const data=await api(query('/api/layout',{process:state.process,run:state.run}));state.layout=data;state.layers=new Set(data.layers.map(layer=>layer.key));state.layoutZoom=1;state.layoutPan=[0,0];$('layout-count').textContent=`${data.shape_count.toLocaleString()} polygons · ${data.layers.length} layers`;const list=$('layer-list');clear(list);for(const layer of data.layers){const label=add(list,'label',undefined,'layer-row');const input=add(label,'input');input.type='checkbox';input.checked=true;input.dataset.layer=layer.key;const swatch=add(label,'span',undefined,'layer-color');swatch.style.background=layer.color;add(label,'span',layer.name);add(label,'span',layer.count,'count');input.addEventListener('change',()=>{input.checked?state.layers.add(layer.key):state.layers.delete(layer.key);drawLayout();});}requestAnimationFrame(drawLayout);}
function layoutTransform(w,h,bbox){const [x0,y0,x1,y1]=bbox,scale=Math.min((w-80)/(x1-x0),(h-80)/(y1-y0))*state.layoutZoom,cx=(x0+x1)/2,cy=(y0+y1)/2;return {x:v=>w/2+(v-cx)*scale+state.layoutPan[0],y:v=>h/2-(v-cy)*scale+state.layoutPan[1],inverseX:px=>(px-w/2-state.layoutPan[0])/scale+cx,inverseY:py=>-(py-h/2-state.layoutPan[1])/scale+cy};}
function drawLayout(){const data=state.layout;if(!data||state.view!=='layout')return;const canvas=$('layout-canvas'),{ctx,w,h}=canvasSetup(canvas),tr=layoutTransform(w,h,data.bbox);ctx.fillStyle='#081b26';ctx.fillRect(0,0,w,h);ctx.strokeStyle='#173340';ctx.lineWidth=1;for(let x=0;x<w;x+=30){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke();}for(let y=0;y<h;y+=30){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();}for(const layer of data.layers){if(!state.layers.has(layer.key))continue;ctx.fillStyle=layer.color+'99';ctx.strokeStyle=layer.color;ctx.lineWidth=1;for(const poly of layer.polygons){ctx.beginPath();for(const [i,ring] of [poly.hull,...poly.holes].entries()){for(let j=0;j<ring.length;j++){const [x,y]=ring[j];if(j===0)ctx.moveTo(tr.x(x),tr.y(y));else ctx.lineTo(tr.x(x),tr.y(y));}ctx.closePath();}ctx.fill('evenodd');ctx.stroke();}}canvas._layoutTransform=tr;}
function renderDocList(){const list=$('doc-list');clear(list);for(const name of state.overview.documents){const button=add(list,'button',name,'doc-item');button.type='button';button.dataset.doc=name;button.addEventListener('click',()=>loadDoc(name).catch(err=>notice(err.message,true)));}}
async function loadDoc(name){const data=await api(query('/api/document',{name}));state.doc=name;for(const el of document.querySelectorAll('.doc-item'))el.classList.toggle('active',el.dataset.doc===name);renderMarkdown(data.text,$('doc-body'));}
function inlineMarkdown(parent,text){
  const pattern=/\[([^\]]+)\]\(([^)]+)\)|`([^`]+)`|\*\*([^*]+)\*\*/g;
  let start=0,match;
  while((match=pattern.exec(text))){
    if(match.index>start)parent.append(document.createTextNode(text.slice(start,match.index)));
    if(match[1]){
      const raw=match[2].split('#')[0];
      const local=new URL(raw,`http://localhost/${state.doc||'README.md'}`).pathname.slice(1);
      if(state.overview.documents.includes(local)){
        const link=add(parent,'a',match[1]);link.href='#';link.addEventListener('click',event=>{event.preventDefault();loadDoc(local).catch(err=>notice(err.message,true));});
      }else if(/^https?:\/\//.test(match[2])){
        const link=add(parent,'a',match[1]);link.href=match[2];link.target='_blank';link.rel='noopener noreferrer';
      }else parent.append(document.createTextNode(match[1]));
    }else if(match[3])add(parent,'code',match[3]);
    else add(parent,'strong',match[4]);
    start=pattern.lastIndex;
  }
  if(start<text.length)parent.append(document.createTextNode(text.slice(start)));
}
function renderMarkdown(source,root){
  clear(root);let inCode=false,code=[],paragraph=[],table=null;
  function flush(){if(paragraph.length){inlineMarkdown(add(root,'p'),paragraph.join(' '));paragraph=[];}}
  function flushCode(){if(code.length){add(root,'pre',code.join('\n'));code=[];}}
  for(const line of source.split('\n')){
    if(line.startsWith('```')){flush();if(inCode)flushCode();inCode=!inCode;table=null;continue;}
    if(inCode){code.push(line);continue;}
    if(/^\s*\|/.test(line)){
      flush();if(/^\s*\|[\s:|-]+\|\s*$/.test(line))continue;
      if(!table)table=add(root,'table');
      const cells=line.trim().replace(/^\||\|$/g,'').split('|');const row=add(table,'tr');
      for(const cell of cells)inlineMarkdown(add(row,table.rows.length===1?'th':'td'),cell.trim());
      continue;
    }
    table=null;
    const heading=line.match(/^(#{1,4})\s+(.*)$/);
    if(heading){flush();inlineMarkdown(add(root,`h${heading[1].length}`),heading[2]);continue;}
    if(/^\s*[-*]\s+/.test(line)){flush();inlineMarkdown(add(root,'div',undefined,'doc-bullet'),'• '+line.replace(/^\s*[-*]\s+/,''));continue;}
    if(!line.trim()){flush();continue;}
    paragraph.push(line);
  }
  flush();flushCode();
}
async function loadSchematic(){
  if(!state.report)return;
  const process=state.process;
  $('editor-status').textContent='Netlisting and rendering Xschem source in the local worker…';
  const data=await api(query('/api/schematic',{process}));
  if(process!==state.process)return;
  if(state.schematic?.source_sha256&&state.schematic.source_sha256!==data.source_sha256){state.editorExperiment=null;$('schematic-sim-status').textContent='Source changed; run a new exploratory simulation.';}
  state.schematic=data;
  $('editor-source').textContent=data.source;
  $('xschem-netlist').textContent=data.netlist;
  $('xschem-image').src=query('/api/schematic.svg',{process,sha:data.preview_sha256});
  $('editor-status').textContent=`${data.recognized_inverter?'Two-transistor inverter connectivity recognized':'Schematic changed: inspect generated netlist'} · ${data.native_editor_available?'native Xschem ready':'native Xschem GUI unavailable'}`;
  const simulators=$('simulator-status');clear(simulators);
  add(simulators,'div',data.ngspice_executable_found?'ngspice: installed on this Mac; worker testbench runs are available.':'ngspice: unavailable on this Mac.','interpretation-item');
  add(simulators,'div',data.spectre_executable_found?'Spectre executable found; license and compatible model validation are still required.':'Spectre: no executable found on this Mac. Licensed Cadence access and compatible models are required.','interpretation-item');
  $('open-xschem').disabled=!data.native_editor_available;
  $('open-xschem').title=data.native_editor_available?'Open this .sch in native Xschem':'Start XQuartz and refresh the schematic to enable the native editor';
}
function attachSchematicEvents(){
  for(const button of document.querySelectorAll('[data-schematic-view]'))button.addEventListener('click',()=>{
    state.schematicView=button.dataset.schematicView;
    for(const el of document.querySelectorAll('[data-schematic-view]'))el.classList.toggle('selected',el===button);
    $('functional-schematic').toggleAttribute('hidden',state.schematicView!=='functional');
    $('xschem-image').hidden=state.schematicView!=='xschem';
  });
  $('refresh-schematic').addEventListener('click',()=>loadSchematic().catch(err=>notice(err.message,true)));
  $('copy-schematic-path').addEventListener('click',()=>navigator.clipboard.writeText($('editor-source').textContent).then(()=>notice('Schematic source path copied.')).catch(err=>notice(err.message,true)));
  $('open-xschem').addEventListener('click',async()=>{
    try{
      const data=await api('/api/open-xschem',{method:'POST',headers:{'Content-Type':'application/json','X-Lab-Token':state.overview.token},body:JSON.stringify({process:state.process})});
      notice(`Opened native Xschem: ${data.source}`);
    }catch(err){notice(err.message,true);}
  });
  $('simulate-schematic').addEventListener('click',async event=>{
    if(!state.schematic)return notice('Refresh the Xschem source first.',true);
    const button=event.currentTarget;button.disabled=true;$('schematic-sim-status').textContent='Running source netlist in offline ngspice worker…';
    try{
      const body={process:state.process,source_sha256:state.schematic.source_sha256};
      const result=await api('/api/simulate-schematic',{method:'POST',headers:{'Content-Type':'application/json','X-Lab-Token':state.overview.token},body:JSON.stringify(body)});
      state.editorExperiment=result;$('schematic-sim-status').textContent=`Exploratory run ${result.manifest.id.slice(0,8)} · source ${result.manifest.schematic_sha256.slice(0,12)} · ${result.samples.length.toLocaleString()} samples`;
      requestAnimationFrame(()=>drawPlot($('schematic-canvas'),result.samples));
      notice('Edited Xschem source simulated; DRC/LVS/PEX evidence remains tied to its selected validation run.');
    }catch(err){$('schematic-sim-status').textContent='Simulation failed';notice(err.message,true);}finally{button.disabled=false;}
  });
}
function configureEvidenceSelectors(){
  const drc=$('drc-variant'),lvs=$('lvs-variant');clear(drc);clear(lvs);
  const drcOptions=state.process==='gf180'?[['connected','Connected layout · passing'],['default_pcell','Default PCell · 20 errors'],['probe','Disconnected probe · DRC clean']]:[['connected','Connected layout · passing']];
  const lvsOptions=state.process==='gf180'?[['connected','Connected layout · match'],['disconnected_probe','Disconnected probe · mismatch'],['wrong_bulk','Wrong bulk · mismatch']]:[['connected','Connected layout · match'],['wrong_reference','Wrong reference · mismatch']];
  for(const [value,label] of drcOptions){const option=add(drc,'option',label);option.value=value;}
  for(const [value,label] of lvsOptions){const option=add(lvs,'option',label);option.value=value;}
}
async function loadEvidence(){await Promise.all([loadDrc(),loadLvs()]);}
async function loadDrc(){
  if(!state.report)return;
  const variant=$('drc-variant').value,fields={process:state.process,run:state.run,variant};
  $('drc-summary').textContent='Reading marker database and GDS…';
  const [drc,layout]=await Promise.all([api(query('/api/drc',fields)),api(query('/api/layout',fields))]);
  if(state.run!==fields.run||state.process!==fields.process||$('drc-variant').value!==variant)return;
  state.drc=drc;state.drcLayout=layout;state.drcFocus=null;
  const label=variant==='default_pcell'?'Deliberately failing default PCell':variant==='probe'?'Disconnected probe':'Connected layout';
  $('drc-summary').textContent=`${label}: ${drc.count} KLayout marker${drc.count===1?'':'s'} · GDS ${drc.gds_sha256.slice(0,12)} · report ${drc.rdb_sha256.slice(0,12)}`;
  const list=$('drc-marker-list');clear(list);
  if(!drc.markers.length)add(list,'div','No markers in this report. Select the GF180 default PCell to inspect a failing DRC control.','empty-state');
  for(const marker of drc.markers){
    const button=add(list,'button',undefined,'marker-item');button.type='button';
    add(button,'strong',`${marker.index}. ${marker.rule}`);add(button,'span',marker.description);
    if(marker.bbox)add(button,'small',`x ${marker.bbox[0].toFixed(3)}–${marker.bbox[2].toFixed(3)} µm · y ${marker.bbox[1].toFixed(3)}–${marker.bbox[3].toFixed(3)} µm`);
    button.addEventListener('click',()=>{state.drcFocus=marker.bbox;for(const el of list.querySelectorAll('.marker-item'))el.classList.toggle('selected',el===button);drawDrc();});
  }
  requestAnimationFrame(drawDrc);
}
function drawDrc(){
  if(state.view!=='verification'||!state.drcLayout)return;
  const canvas=$('drc-canvas'),{ctx,w,h}=canvasSetup(canvas),data=state.drcLayout;
  ctx.fillStyle='#091d28';ctx.fillRect(0,0,w,h);
  let [x0,y0,x1,y1]=state.drcFocus||data.bbox;
  const width=Math.max(x1-x0,.4),height=Math.max(y1-y0,.4),margin=state.drcFocus?2:.15;
  x0-=width*margin;x1+=width*margin;y0-=height*margin;y1+=height*margin;
  const scale=Math.min((w-40)/(x1-x0),(h-40)/(y1-y0)),cx=(x0+x1)/2,cy=(y0+y1)/2;
  const x=value=>w/2+(value-cx)*scale,y=value=>h/2-(value-cy)*scale;
  ctx.strokeStyle='#21404a';ctx.lineWidth=1;
  for(let px=0;px<w;px+=30){ctx.beginPath();ctx.moveTo(px,0);ctx.lineTo(px,h);ctx.stroke();}
  for(let py=0;py<h;py+=30){ctx.beginPath();ctx.moveTo(0,py);ctx.lineTo(w,py);ctx.stroke();}
  for(const layer of data.layers){
    ctx.fillStyle=layer.color+'55';ctx.strokeStyle=layer.color+'aa';
    for(const poly of layer.polygons){ctx.beginPath();for(const ring of [poly.hull,...poly.holes]){for(let i=0;i<ring.length;i++){const [px,py]=ring[i];if(i===0)ctx.moveTo(x(px),y(py));else ctx.lineTo(x(px),y(py));}ctx.closePath();}ctx.fill('evenodd');ctx.stroke();}
  }
  for(const marker of state.drc?.markers||[]){
    if(!marker.bbox)continue;
    const [mx0,my0,mx1,my1]=marker.bbox,left=Math.min(x(mx0),x(mx1)),top=Math.min(y(my0),y(my1));
    const mw=Math.max(12,Math.abs(x(mx1)-x(mx0))),mh=Math.max(12,Math.abs(y(my1)-y(my0)));
    ctx.strokeStyle='#ff746e';ctx.lineWidth=2;ctx.fillStyle='#ff746e22';ctx.fillRect(left-5,top-5,mw+10,mh+10);ctx.strokeRect(left-5,top-5,mw+10,mh+10);
    ctx.fillStyle='#ffe1d5';ctx.font='bold 11px ui-monospace,monospace';ctx.fillText(String(marker.index),left-3,top-9);
  }
}
async function loadLvs(){
  if(!state.report)return;
  const variant=$('lvs-variant').value,fields={process:state.process,run:state.run,variant};
  $('lvs-summary').textContent='Reading Netgen comparison…';
  const result=await api(query('/api/lvs',fields));
  if(state.run!==fields.run||state.process!==fields.process||$('lvs-variant').value!==variant)return;
  state.lvs=result;
  const summary=$('lvs-summary');summary.textContent=result.matched?'UNIQUE MATCH · schematic and extracted layout':'MISMATCH · compare the nodes and pins below';summary.className=`evidence-summary ${result.matched?'check-good':'check-bad'}`;
  const box=$('lvs-comparison');clear(box);
  for(const [label,pair] of [['Devices',result.devices],['Nets',result.nets]]){
    const row=add(box,'div',undefined,'lvs-row');add(row,'strong',label);add(row,'span',`Schematic ${pair?.[0]??'—'}`);add(row,'span',`Extracted ${pair?.[1]??'—'}`);
  }
  const list=$('lvs-mismatches');clear(list);
  if(result.matched)add(list,'div','No connectivity mismatches in the selected comparison.','interpretation-item');
  else for(const line of result.mismatches)add(list,'div',line,'mismatch-item');
  const report=await api(query('/api/artifact',{process:state.process,run:state.run,name:result.report}));
  if(state.run===fields.run&&$('lvs-variant').value===variant)$('lvs-report').textContent=report.text;
}
async function loadPex(){
  if(!state.report)return;
  const fields={process:state.process,run:state.run};
  const data=await api(query('/api/pex',fields));
  if(state.run!==fields.run||state.process!==fields.process)return;
  state.pex=data;
  const grid=$('pex-metrics');clear(grid);
  for(const [label,value,sub] of [['Top-level C',`${data.top_total_ff.toFixed(3)} fF`,`${data.capacitors.length} inverter-net capacitors`],['All C',String(data.all_capacitor_count),'includes transistor subcircuits'],['Extracted R',String(data.resistor_count),'distributed wire R absent'],['Delay penalty',`+${data.delay_delta_ps.tphl?.toFixed(2)??'—'} ps`,'tPHL vs schematic']]){
    const card=add(grid,'div',undefined,'metric-card');add(card,'div',label,'label');add(card,'div',value,'value');add(card,'div',sub,'sub');
  }
  const table=$('pex-capacitors');clear(table);const head=add(table,'div',undefined,'pex-row head');for(const name of ['Element','Node A','Node B','fF'])add(head,'span',name);
  for(const capacitor of data.capacitors){const row=add(table,'div',undefined,'pex-row');for(const value of [capacitor.name,capacitor.a,capacitor.b,capacitor.ff.toFixed(5)])add(row,'span',value);}
  const scope=$('pex-scope');clear(scope);for(const item of [data.scope,'Compare delays using the same model corner, input and load.','This is simulation evidence, not silicon measurement.'])add(scope,'div',item,'interpretation-item');
  const netlist=await api(query('/api/artifact',{...fields,name:data.netlist}));
  if(state.run===fields.run)$('pex-netlist').textContent=netlist.text;
}
function attachEvidenceEvents(){
  $('drc-variant').addEventListener('change',()=>loadDrc().catch(err=>notice(err.message,true)));
  $('lvs-variant').addEventListener('change',()=>loadLvs().catch(err=>notice(err.message,true)));
  $('open-klayout').addEventListener('click',async event=>{
    const button=event.currentTarget;button.disabled=true;
    try{
      const body={process:state.process,run:state.run,variant:$('drc-variant').value};
      const result=await api('/api/open-klayout',{method:'POST',headers:{'Content-Type':'application/json','X-Lab-Token':state.overview.token},body:JSON.stringify(body)});
      notice(`Opened ${result.variant.replace('_',' ')} GDS and marker database in native KLayout.`);
    }catch(err){notice(err.message,true);}finally{button.disabled=false;}
  });
  $('copy-pex').addEventListener('click',()=>navigator.clipboard.writeText($('pex-netlist').textContent).then(()=>notice('PEX netlist copied.')).catch(err=>notice(err.message,true)));
}
async function simulate(event){event.preventDefault();const button=event.currentTarget.querySelector('button[type=submit]');button.disabled=true;$('experiment-status').textContent='Running ngspice on local worker…';try{const body={process:state.process,voltage:Number($('exp-voltage').value),load_ff:Number($('exp-load').value),temp_c:Number($('exp-temp').value)};const data=await api('/api/simulate',{method:'POST',headers:{'Content-Type':'application/json','X-Lab-Token':state.overview.token},body:JSON.stringify(body)});state.experiment=data;const m=data.manifest;$('experiment-status').textContent='Exploratory run saved';$('experiment-id').textContent=`Experiment ${m.id}`;const box=$('experiment-result');clear(box);for(const [label,value] of [['Process',state.overview.processes[m.process].title],['Supply',`${m.voltage} V`],['Load',`${m.load_ff} fF`],['Temperature',`${m.temp_c} °C`],['VOUT at 0.5 ns',`${m.high_v.toFixed(4)} V`],['VOUT at 2.0 ns',`${m.low_v.toFixed(4)} V`]]){const row=add(box,'div',undefined,'result-line');add(row,'span',label);add(row,'strong',value);}requestAnimationFrame(()=>drawPlot($('experiment-canvas'),data.samples));notice(`Exploratory run ${m.id.slice(0,8)} saved locally.`);}catch(err){$('experiment-status').textContent='Simulation failed';notice(err.message,true);}finally{button.disabled=false;}}
async function rerun(){const button=$('rerun-button');button.disabled=true;try{const data=await api('/api/validate',{method:'POST',headers:{'Content-Type':'application/json','X-Lab-Token':state.overview.token},body:JSON.stringify({process:state.process})});notice('Full validation pipeline started. Checking the new report…');while(true){await new Promise(resolve=>setTimeout(resolve,2000));const job=await api(query('/api/job',{id:data.job_id}));if(job.state==='running')continue;if(job.state==='complete'){state.overview=await api('/api/overview');selectRun();await loadRun();notice(`Mac validation finished: ${job.report_status||'inspect report'} · ${job.run_id?.slice(0,8)||'no report'}`);}else notice(`Validation failed: ${job.output||'inspect worker logs'}`,true);break;}}catch(err){notice(err.message,true);}finally{button.disabled=false;}}
function attachEvents(){$('process-select').addEventListener('change',async event=>{state.process=event.target.value;state.experiment=null;$('experiment-result').innerHTML='<div class="empty-state">Adjust a parameter and simulate to see a new trace.</div>';$('experiment-status').textContent='Ready to simulate';$('exp-voltage').value=state.overview.processes[state.process].voltage;selectRun();await loadRun();});$('run-select').addEventListener('change',async event=>{state.run=event.target.value;await loadRun();});for(const button of document.querySelectorAll('[data-view]'))button.addEventListener('click',()=>setView(button.dataset.view));for(const button of document.querySelectorAll('[data-goto]'))button.addEventListener('click',()=>setView(button.dataset.goto));for(const button of document.querySelectorAll('[data-wave]'))button.addEventListener('click',()=>{state.waveKind=button.dataset.wave;for(const el of document.querySelectorAll('[data-wave]'))el.classList.toggle('selected',el===button);loadWave().catch(err=>notice(err.message,true));});$('copy-netlist').addEventListener('click',()=>navigator.clipboard.writeText($('schematic-code').textContent).then(()=>notice('Netlist copied.')).catch(err=>notice(err.message,true)));$('open-artifact').addEventListener('click',async()=>{try{const data=await api(query('/api/artifact',{process:state.process,run:state.run,name:$('artifact-select').value}));$('artifact-content').textContent=data.text;}catch(err){notice(err.message,true);}});$('experiment-form').addEventListener('submit',simulate);$('rerun-button').addEventListener('click',rerun);$('fit-layout').addEventListener('click',()=>{state.layoutZoom=1;state.layoutPan=[0,0];drawLayout();});$('toggle-layers').addEventListener('click',()=>{const all=state.layers.size!==state.layout.layers.length;state.layers=new Set(all?state.layout.layers.map(layer=>layer.key):[]);for(const input of document.querySelectorAll('[data-layer]'))input.checked=all;drawLayout();});const canvas=$('layout-canvas');canvas.addEventListener('wheel',event=>{event.preventDefault();state.layoutZoom=Math.max(.35,Math.min(12,state.layoutZoom*(event.deltaY<0?1.17:.85)));drawLayout();},{passive:false});canvas.addEventListener('pointerdown',event=>{state.drag=[event.clientX,event.clientY,...state.layoutPan];canvas.setPointerCapture(event.pointerId);});canvas.addEventListener('pointermove',event=>{const rect=canvas.getBoundingClientRect(),tr=canvas._layoutTransform;if(tr)$('layout-coordinates').textContent=`x ${tr.inverseX(event.clientX-rect.left).toFixed(3)} µm · y ${tr.inverseY(event.clientY-rect.top).toFixed(3)} µm`;if(state.drag){state.layoutPan=[state.drag[2]+event.clientX-state.drag[0],state.drag[3]+event.clientY-state.drag[1]];drawLayout();}});canvas.addEventListener('pointerup',()=>state.drag=null);$('wave-canvas').addEventListener('mousemove',plotHover);$('wave-canvas').addEventListener('mouseleave',()=>$('wave-tooltip').hidden=true);window.addEventListener('resize',()=>{if(state.view==='layout')drawLayout();if(state.view==='waveforms'&&state.wave)drawPlot($('wave-canvas'),state.wave.samples);if(state.view==='experiments'&&state.experiment)drawPlot($('experiment-canvas'),state.experiment.samples);});}
async function init(){try{state.overview=await api('/api/overview');const select=$('process-select');for(const [id,spec] of Object.entries(state.overview.processes)){const opt=add(select,'option',spec.title);opt.value=id;}select.value=state.process;$('exp-voltage').value=state.overview.processes[state.process].voltage;selectRun();renderDocList();attachEvents();attachEvidenceEvents();attachSchematicEvents();await loadRun();}catch(err){notice(`Dashboard failed to load: ${err.message}`,true);}}
init();
