const $ = id => document.getElementById(id);
const state = {overview:null,process:'sky130',run:null,report:null,view:'overview',circuit:'inverter',rco:null,rcoRun:null,rcoSignals:new Set([1,2,3,4]),rcoProbe:null,rcoIntervalStart:null,rcoIntervalEnd:null,waveKind:'schematic',waveSignals:new Set(['in','out']),wave:null,analysis:null,analysisPromise:null,layout:null,rcLayout:null,rcSelection:null,rcShowR:true,rcShowC:false,rcNet:'all',comparison:null,comparisonRun:null,comparisonZoom:1,comparisonPan:[0,0],comparisonProbe:null,comparisonHighlight:true,layers:new Set(),doc:null,experiment:null,plot:null,layoutZoom:1,layoutPan:[0,0],drag:null,drc:null,drcLayout:null,drcFocus:null,lvs:null,pex:null,pexBench:null,schematic:null,editorExperiment:null,checkpoints:[]};

async function api(path, options={}, retried=false) {
  const response = await fetch(path, options);
  const data = await response.json();
  if(!response.ok && !retried && data.error==='Missing dashboard session token' && options.method==='POST'){
    const fresh=await fetch('/api/overview').then(reply=>reply.json());
    state.overview.token=fresh.token;
    return api(path,{...options,headers:{...options.headers,'X-Lab-Token':fresh.token}},true);
  }
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}
const query = (path, fields) => `${path}?${new URLSearchParams(fields)}`;
function notice(message, error=false) { const el=$('notice'); el.textContent=message; el.classList.toggle('error',error); el.hidden=false; clearTimeout(notice.timer); notice.timer=setTimeout(()=>el.hidden=true,8500); }
function clear(node){node.replaceChildren();}
function add(parent,tag,text,className){const el=document.createElement(tag); if(text!==undefined)el.textContent=String(text); if(className)el.className=className; parent.append(el);return el;}
function fmtPs(value){return Number.isFinite(value)?`${(value*1e12).toFixed(2)} ps`:'—';}
function metric(checks,kind){return kind==='schematic'?(checks.baseline||checks.schematic_simulation):kind==='rcx'?(checks.rc_extracted||checks.rc_extracted_simulation):(checks.capacitance_extracted||checks.capacitance_extracted_simulation);}
function drcValue(){const c=state.report?.checks||{};return state.process==='sky130'?c.native_klayout_drc_items:c.native_klayout_connected_full_drc_items;}
function magicValue(){const c=state.report?.checks||{};return state.process==='sky130'?c.magic_full_drc_errors:c.magic_connected_drc_errors;}
function lvsValue(){const c=state.report?.checks||{};return state.process==='sky130'?c.lvs:c.connected_lvs;}
function selectRun(){const options=state.overview.runs[state.process]||[];const select=$('run-select');clear(select);for(const item of options){const opt=add(select,'option',`${item.status.toUpperCase()} · ${item.layout_variant||'legacy'} · ${item.id.slice(0,8)}`);opt.value=item.id;}const chosen=options.find(item=>item.status==='passed')||options[0];state.run=chosen?.id||null;select.value=state.run||'';}
async function loadRun(){if(!state.run){state.report=null;notice('No validation runs found for this process.',true);return;}if($('checkpoint-dialog').open)$('checkpoint-dialog').close();state.report=await api(query('/api/run',{process:state.process,run:state.run}));state.wave=null;state.analysis=null;state.analysisPromise=null;state.layout=null;state.rcLayout=null;state.rcSelection=null;state.comparison=null;state.comparisonRun=null;state.comparisonProbe=null;state.drc=null;state.drcLayout=null;state.lvs=null;state.pex=null;state.pexBench=null;state.schematic=null;state.editorExperiment=null;state.layers.clear();const rcx=!!state.report.checks?.rc_network;for(const el of document.querySelectorAll('[data-wave="rcx"],#testbench-select option[value="rcx"],#pex-kind option[value="rcx"]'))el.disabled=!rcx;if(!rcx&&state.waveKind==='rcx')state.waveKind='postlayout';if(!rcx&&$('pex-kind').value==='rcx')$('pex-kind').value='postlayout';for(const el of document.querySelectorAll('[data-wave]'))el.classList.toggle('selected',el.dataset.wave===state.waveKind);renderOverview();renderSchematic();renderVerification();configureEvidenceSelectors();if(state.view==='waveforms')await loadWave();if(state.view==='layout')await loadLayout();if(state.view==='verification')await loadEvidence();if(state.view==='pex')await loadPex();if(state.view==='schematic')await loadSchematic();}
function checkpointRow(parent,item){const button=add(parent,'button',undefined,'pipeline-item pipeline-action');button.type='button';button.dataset.checkpoint=item.id;button.setAttribute('aria-haspopup','dialog');button.setAttribute('aria-label',`Inspect ${item.title} checkpoint`);add(button,'strong',item.title);const right=add(button,'span',undefined,'pipeline-right');add(right,'span',item.status,item.cls);add(right,'span','›','pipeline-chevron');}
function checkpointData(){
  const report=state.report,c=report.checks||{},sch=metric(c,'schematic')||{},post=metric(c,'postlayout')||{},rc=metric(c,'rcx')||{},evidence=report.evidence_sha256||{};
  const gf=state.process==='gf180',gds=gf?'connected/inverter.gds':'inverter.gds',pex=gf?'connected/inverter_pex.spice':'inverter_pex.spice',postdeck=gf?'connected/postlayout.spice':'postlayout.spice',rcnet=gf?'connected/rcx/inverter_rcx.spice':'rcx/inverter_rcx.spice',rcdeck=gf?'connected/rcx/postlayout_rcx.spice':'rcx/postlayout_rcx.spice';
  const files=names=>names.filter(name=>Object.hasOwn(evidence,name));
  const good='check-good',warn='check-warn';
  return [
    {id:'schematic',title:'Schematic simulation',status:Number.isFinite(sch.tphl)?'Measured':'Missing',cls:Number.isFinite(sch.tphl)?good:warn,description:'The pinned inverter testbench drives the input pulse and 5 fF output load with the selected PDK models.',facts:[['Corner',state.overview.processes[state.process].corner],['tPHL',fmtPs(sch.tphl)],['tPLH',fmtPs(sch.tplh)]],files:files(['inverter.spice','baseline.log']),view:'waveforms',waveKind:'schematic'},
    {id:'layout',title:'Connected layout',status:evidence[gds]?'GDS recorded':'Missing',cls:evidence[gds]?good:warn,description:'The connected inverter geometry was exported to GDS. Open the layout view to inspect its actual polygons.',facts:[['Top cell','inverter'],['GDS',gds],['KLayout readback',c.native_klayout_readback?`${c.native_klayout_readback.layers} layers`:'Unrecorded']],files:files([gds,'layout.tcl']),view:'layout'},
    {id:'magic',title:'Magic DRC',status:magicValue()===0?'0 errors':magicValue()==null?'Unknown':`${magicValue()} errors`,cls:magicValue()===0?good:warn,description:'Magic checked the connected layout with this process configuration. Zero errors applies to this deck and geometry only.',facts:[['Connected errors',magicValue()??'Unknown'],['Negative control',c.negative_drc_errors??c.magic_default_pcell_drc_errors??'Unrecorded']],files:files([gf?'magic_connected.log':'magic.log']),view:'verification'},
    {id:'klayout',title:'Native KLayout DRC',status:drcValue()===0?'0 items':drcValue()==null?'Unknown':`${drcValue()} items`,cls:drcValue()===0?good:warn,description:'The native Mac KLayout run checked the connected GDS with its PDK rule deck and saved the marker database.',facts:[['Marker items',drcValue()??'Unknown'],['Host',report.host?.system||'Unrecorded']],files:files([gf?'connected/main.lyrdb':'klayout_drc.xml',gf?'klayout_connected_main.log':'klayout.log']),view:'verification'},
    {id:'lvs',title:'Netgen LVS',status:lvsValue()?.includes('unique match')?'Unique match':'Inspect run',cls:lvsValue()?.includes('unique match')?good:warn,description:'Netgen compared the schematic reference with the extracted connected layout. The DRC/LVS view also has deliberate failing controls.',facts:[['Result',lvsValue()||'Unrecorded'],['Counts',lvsValue()?.includes('unique match')?'2 devices / 4 nets in each circuit':'Read the Netgen report']],files:files([gf?'connected/lvs_report.txt':'lvs_report.txt','schematic.spice']),view:'verification'},
    {id:'pex',title:'Capacitance PEX',status:Number.isFinite(post.tphl)&&evidence[pex]?'Measured':'Missing',cls:Number.isFinite(post.tphl)&&evidence[pex]?good:warn,description:'Magic extracted device geometry and capacitance. The post-layout testbench replaces the schematic devices with the extracted inverter while retaining the stimulus and load.',facts:[['tPHL',fmtPs(post.tphl)],['tPLH',fmtPs(post.tplh)],['ΔtPHL',fmtPs(post.tphl-sch.tphl)],['Scope','Capacitance only']],files:files([pex,postdeck,'postlayout.log']),view:'waveforms',waveKind:'postlayout'},
    {id:'rcx',title:'Distributed wire R-C',status:Number.isFinite(rc.tphl)&&evidence[rcnet]?'Measured':'Missing',cls:Number.isFinite(rc.tphl)&&evidence[rcnet]?good:warn,description:'Magic flattened a private copy of the connected cell, split its nets into explicit resistor segments, and simulated the extracted R-C network. Flattening also changes extracted capacitance; the difference from C-only is not resistance alone.',facts:[['Wire resistors',c.rc_network?.resistor_count??'Unrecorded'],['tPHL',fmtPs(rc.tphl)],['tPLH',fmtPs(rc.tplh)],['ΔtPHL vs C only',fmtPs(rc.tphl-post.tphl)],['Scope','Open-PDK engineering extraction']],files:files([rcnet,rcdeck,'magic_rcx.log','postlayout_rcx.log']),view:'waveforms',waveKind:'rcx'}
  ];
}
function renderOverview(){const report=state.report;if(!report)return;const c=report.checks||{},spec=state.overview.processes[state.process],sch=metric(c,'schematic')||{},pex=metric(c,'postlayout')||{},rc=metric(c,'rcx')||{};const host=report.host?.system==='Darwin'?`Mac ${report.host?.arch||'?'}`:report.host?.system?`${report.host.system} ${report.host?.arch||''} host`:'host unrecorded';$('hero-process').textContent=spec.title;$('hero-subtitle').textContent=`${spec.voltage} V · ${spec.pdk} · ${host}`;$('hero-corner').textContent=spec.corner;$('hero-status').textContent=report.status.toUpperCase();$('hero-status').className='hero-value '+(report.status==='passed'?'check-good':'check-warn');$('hero-run').textContent=state.run;$('hero-drc').textContent=drcValue()===0?'0 DRC items':`${drcValue()??'—'} DRC items`;$('hero-lvs').textContent=lvsValue()||'LVS unavailable';
  const grid=$('metric-grid');clear(grid);const cards=[['Schematic tPHL',fmtPs(sch.tphl),'50% input → output'],['Schematic tPLH',fmtPs(sch.tplh),'50% input → output'],['C-only tPHL',fmtPs(pex.tphl),`Δ ${fmtPs(pex.tphl-sch.tphl)}`],['C-only tPLH',fmtPs(pex.tplh),`Δ ${fmtPs(pex.tplh-sch.tplh)}`]];if(c.rc_network)cards.push(['Wire R-C tPHL',fmtPs(rc.tphl),`Δ vs C-only ${fmtPs(rc.tphl-pex.tphl)}`],['Wire R-C tPLH',fmtPs(rc.tplh),`Δ vs C-only ${fmtPs(rc.tplh-pex.tplh)}`]);for(const [label,val,sub] of cards){const card=add(grid,'div',undefined,'metric-card');add(card,'div',label,'label');add(card,'div',val,'value');add(card,'div',sub,'sub');}
  const pipeline=$('pipeline');clear(pipeline);state.checkpoints=checkpointData();for(const item of state.checkpoints)checkpointRow(pipeline,item);
  const interpretation=$('interpretation');clear(interpretation);const items=[report.scope||'Open PDK lab check',...(report.unresolved||[])];if(state.process==='sky130')items.push(c.rc_network?'Antenna and density were not checked; R-C extraction is open-PDK engineering evidence, not foundry signoff.':'Antenna and density were not checked; distributed wire resistance and foundry qualification remain open.');items.push('R2 provides storage. Remote compute has not been configured.');for(const item of items)add(interpretation,'div',item,'interpretation-item');
}
function openCheckpoint(id){
  const item=state.checkpoints.find(entry=>entry.id===id);if(!item)return;
  const dialog=$('checkpoint-dialog');$('checkpoint-title').textContent=item.title;
  $('checkpoint-status').textContent=item.status;$('checkpoint-status').className=`checkpoint-status ${item.cls}`;
  $('checkpoint-description').textContent=item.description;
  const facts=$('checkpoint-facts');clear(facts);
  for(const [label,value] of item.facts){const row=add(facts,'div',undefined,'checkpoint-fact');add(row,'span',label);add(row,'strong',value);}
  const files=$('checkpoint-files');clear(files);
  if(!item.files.length)add(files,'div','No artifact is recorded for this checkpoint in the selected run.','small-muted');
  for(const name of item.files){
    const row=add(files,'div',undefined,'checkpoint-file');const meta=add(row,'div');add(meta,'strong',name);add(meta,'small',`SHA-256 ${(state.report.evidence_sha256[name]||'').slice(0,16)}…`);
    if(state.report.artifacts?.includes(name)){const button=add(row,'button','Read','small-button');button.type='button';button.addEventListener('click',async()=>{try{const result=await api(query('/api/artifact',{process:state.process,run:state.run,name}));const preview=$('checkpoint-artifact');preview.textContent=result.text;preview.hidden=false;}catch(err){notice(err.message,true);}});}
  }
  $('checkpoint-artifact').hidden=true;$('checkpoint-artifact').textContent='';
  $('checkpoint-run').textContent=`Run ${state.run.slice(0,8)} · ${state.report.pdk_pin?.slice(0,8)||'PDK pin unknown'}`;
  $('checkpoint-open-view').dataset.view=item.view;$('checkpoint-open-view').dataset.waveKind=item.waveKind||'';
  dialog.showModal();
}
function renderSchematic(){const report=state.report;if(!report)return;const spec=state.overview.processes[state.process],list=$('device-params');clear(list);for(const [label,value] of [['Process',spec.title],['Supply',`${spec.voltage} V`],['Corner',spec.corner],['NMOS',`${spec.n_width} × ${spec.channel}`],['PMOS',`${spec.p_width} × ${spec.channel}`],['NMOS symbol',spec.n_symbol||'See Xschem source'],['PMOS symbol',spec.p_symbol||'See Xschem source'],['Output load','5 fF (testbench)']]){const item=add(list,'div',undefined,'parameter-row');add(item,'span',label);add(item,'span',value);}const name='inverter.spice';if(report.artifacts?.includes(name))api(query('/api/artifact',{process:state.process,run:state.run,name})).then(data=>$('schematic-code').textContent=data.text).catch(err=>$('schematic-code').textContent=err.message);else $('schematic-code').textContent='Reference netlist is absent from this run manifest.';}
function renderVerification(){const report=state.report;if(!report)return;const c=report.checks||{},cards=$('verification-cards');clear(cards);for(const [title,value,sub,cls] of [['Magic DRC',`${magicValue()??'—'} errors`,'Worker layout check',magicValue()===0?'check-good':'check-warn'],['Native KLayout',`${drcValue()??'—'} items`,'Full vendor rule deck on Mac',drcValue()===0?'check-good':'check-warn'],['Netgen LVS',lvsValue()?.includes('unique match')?'UNIQUE MATCH':'INSPECT','2 devices · 4 nets',lvsValue()?.includes('unique match')?'check-good':'check-warn']]){const card=add(cards,'div',undefined,'verification-card');add(card,'div',title,'title');add(card,'div',value,`value ${cls}`);add(card,'div',sub,'sub');}
  const checks=$('checks-table');clear(checks);const entries=state.process==='sky130'?[['Connected Magic DRC',c.magic_full_drc_errors===0?'0 errors':'Inspect'],['Connected KLayout DRC',c.native_klayout_drc_items===0?'0 items':'Inspect'],['Negative DRC control',`${c.negative_drc_errors??'—'} error detected`],['Negative LVS control',c.negative_lvs||'—'],['GDS export feedback',String(c.gds_export_feedback??'—')]]:[['Connected Magic DRC',c.magic_connected_drc_errors===0?'0 errors':'Inspect'],['Connected KLayout DRC',c.native_klayout_connected_full_drc_items===0?'0 items':'Inspect'],['Default PCell Magic DRC',`${c.magic_default_pcell_drc_errors??'—'} errors`],['Default PCell KLayout metal1',`${c.native_klayout_default_pcell_metal1_items??'—'} items`],['Disconnected probe LVS',c.probe_lvs||'—'],['Wrong-bulk LVS control',c.negative_lvs||'—']];for(const [label,value] of entries){const item=add(checks,'div',undefined,'check-row');add(item,'span',label);add(item,'strong',value,value==='0 errors'||value==='0 items'?'check-good':value.includes('mismatch')||value.includes('rejected')||value.includes('detected')?'check-warn':'');}
  const limits=$('unresolved-list');clear(limits);const fallback=report.checks?.rc_network?['No antenna or density signoff','Open-PDK R-C extraction is not foundry signoff','No silicon measurement']:['No antenna or density signoff','No distributed wire resistance in extraction','No foundry qualification or silicon measurement'];for(const item of report.unresolved||fallback)add(limits,'div',item,'interpretation-item');const select=$('artifact-select');clear(select);for(const name of report.artifacts||[]){const opt=add(select,'option',name);opt.value=name;}if([...select.options].some(o=>o.value==='inverter.spice'))select.value='inverter.spice';$('artifact-content').textContent='Select an artifact to inspect its text.';}
function rcoRunLabel(item){return `${item.schematic==='xschem'?'Xschem':'Generated'} · ${item.passives==='pdk'?'PDK R/C':item.passives==='pdk_legacy'?'Retired passives':'Ideal R/C'} · ${item.bank_style} · code ${item.code} · MAIN ${item.main?'on':'off'} · ${(item.frequency_hz/1000).toFixed(2)} kHz · ${item.id.slice(0,8)}`;}
function drawRcoPlot(){
  if(state.view!=='rco'||!state.rco?.samples?.length)return;
  const rows=state.rco.samples,canvas=$('rco-canvas'),{ctx,w,h}=canvasSetup(canvas),pad={l:55,r:18,t:20,b:38};
  const x0=rows[0][0],x1=rows[rows.length-1][0],ymax=state.rco.selected.supply_v*1.08;
  const x=t=>pad.l+(t-x0)/(x1-x0)*(w-pad.l-pad.r),y=v=>h-pad.b-v/ymax*(h-pad.t-pad.b);
  ctx.fillStyle='#091c27';ctx.fillRect(0,0,w,h);ctx.strokeStyle='#294b58';ctx.fillStyle='#91afbb';ctx.lineWidth=1;ctx.font='11px ui-monospace,monospace';
  for(let i=0;i<=5;i++){const xx=pad.l+i*(w-pad.l-pad.r)/5;ctx.beginPath();ctx.moveTo(xx,pad.t);ctx.lineTo(xx,h-pad.b);ctx.stroke();ctx.fillText((x0+(x1-x0)*i/5).toFixed(1),xx-12,h-12);}
  for(let i=0;i<=4;i++){const yy=pad.t+i*(h-pad.t-pad.b)/4;ctx.beginPath();ctx.moveTo(pad.l,yy);ctx.lineTo(w-pad.r,yy);ctx.stroke();ctx.fillText((ymax*(1-i/4)).toFixed(1),8,yy+4);}
  ctx.beginPath();ctx.strokeStyle='#d9d06e';ctx.setLineDash([5,4]);ctx.moveTo(pad.l,y(state.rco.selected.supply_v/2));ctx.lineTo(w-pad.r,y(state.rco.selected.supply_v/2));ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#d9d06e';ctx.fillText('½ VDD reference',w-120,y(state.rco.selected.supply_v/2)-6);
  ctx.save();ctx.beginPath();ctx.rect(pad.l,pad.t,w-pad.l-pad.r,h-pad.t-pad.b);ctx.clip();
  for(const [col,color] of [[1,'#5ad9e9'],[2,'#d4a6ff'],[3,'#98e4a7'],[4,'#f6b76a']]){
    if(!state.rcoSignals.has(col))continue;
    ctx.beginPath();ctx.strokeStyle=color;ctx.lineWidth=col===4?2.5:1.6;
    rows.forEach((row,i)=>i?ctx.lineTo(x(row[0]),y(row[col])):ctx.moveTo(x(row[0]),y(row[col])));ctx.stroke();
  }ctx.restore();drawRcoGuides(ctx,rows,x,pad.t,h-pad.b);
}
function drawRcoGuides(ctx,rows,x,top,bottom){
  const first=state.rcoIntervalStart,last=state.rcoIntervalEnd;
  if(first!=null&&last!=null){ctx.fillStyle='#5ce1cb25';ctx.fillRect(x(rows[Math.min(first,last)][0]),top,x(rows[Math.max(first,last)][0])-x(rows[Math.min(first,last)][0]),bottom-top);}
  for(const [index,color] of [[first,'#5ce1cb'],[last,'#e6a0df'],[state.rcoProbe,'#ffffff']]){if(index==null||!rows[index])continue;ctx.beginPath();ctx.strokeStyle=color;ctx.setLineDash(color==='#ffffff'?[4,4]:[]);ctx.moveTo(x(rows[index][0]),top);ctx.lineTo(x(rows[index][0]),bottom);ctx.stroke();ctx.setLineDash([]);}
}
function drawRcoCurrent(){
  if(state.view!=='rco'||!state.rco?.samples?.length)return;
  const rows=state.rco.samples,canvas=$('rco-current-canvas'),{ctx,w,h}=canvasSetup(canvas),pad={l:55,r:18,t:18,b:35};
  ctx.fillStyle='#091c27';ctx.fillRect(0,0,w,h);ctx.fillStyle='#91afbb';ctx.strokeStyle='#294b58';ctx.font='11px ui-monospace,monospace';
  if(rows[0].length<6){ctx.fillText('Supply-current samples are unavailable in this saved run. Rerun the testbench to record them.',18,42);return;}
  const values=rows.map(row=>row[5]*1e6),lo=Math.min(0,...values),hi=Math.max(0,...values),span=Math.max(1,hi-lo),bottom=lo-.05*span,top=hi+.05*span;
  const x=t=>pad.l+(t-rows[0][0])/(rows[rows.length-1][0]-rows[0][0])*(w-pad.l-pad.r),y=v=>h-pad.b-(v-bottom)/(top-bottom)*(h-pad.t-pad.b);
  for(let i=0;i<=4;i++){const yy=pad.t+i*(h-pad.t-pad.b)/4;ctx.beginPath();ctx.moveTo(pad.l,yy);ctx.lineTo(w-pad.r,yy);ctx.stroke();ctx.fillText((top-(top-bottom)*i/4).toFixed(0),5,yy+4);}
  for(let i=0;i<=4;i++){const xx=pad.l+i*(w-pad.l-pad.r)/4;ctx.beginPath();ctx.moveTo(xx,pad.t);ctx.lineTo(xx,h-pad.b);ctx.stroke();ctx.fillText((rows[0][0]+(rows[rows.length-1][0]-rows[0][0])*i/4).toFixed(1),xx-12,h-11);}
  ctx.fillText('µA',6,12);ctx.beginPath();ctx.strokeStyle='#f6b76a';ctx.lineWidth=1.5;rows.forEach((row,i)=>i?ctx.lineTo(x(row[0]),y(row[5]*1e6)):ctx.moveTo(x(row[0]),y(row[5]*1e6)));ctx.stroke();drawRcoGuides(ctx,rows,x,pad.t,h-pad.b);
}
function rcoSampleAt(event){const rows=state.rco?.samples;if(!rows?.length)return null;const rect=event.currentTarget.getBoundingClientRect(),fraction=Math.max(0,Math.min(1,(event.clientX-rect.left-55)/(rect.width-73))),time=rows[0][0]+fraction*(rows[rows.length-1][0]-rows[0][0]);let low=0,high=rows.length-1;while(low<high){const middle=(low+high)>>1;if(rows[middle][0]<time)low=middle+1;else high=middle;}return low>0&&Math.abs(rows[low-1][0]-time)<Math.abs(rows[low][0]-time)?low-1:low;}
function inspectRcoWave(index){
  const rows=state.rco?.samples;if(!rows?.[index])return;state.rcoProbe=index;
  const row=rows[index],before=rows[Math.max(0,index-1)],after=rows[Math.min(rows.length-1,index+1)],slope=(after[1]-before[1])/(after[0]-before[0]||1),threshold=state.rco.selected.supply_v/2;
  const direction=slope>.02?'charging':slope<-.02?'discharging':'nearly flat',near=Math.abs(row[1]-threshold)<.15*state.rco.selected.supply_v;
  const voltage=`t = ${row[0].toFixed(3)} µs · RC0 ${row[1].toFixed(3)} V · RC1 ${row[2].toFixed(3)} V · RC2 ${row[3].toFixed(3)} V · CLK ${row[4].toFixed(3)} V.`;
  const current=row.length>5?` Core supply draw ${((row[5])*1e6).toFixed(2)} µA.`:' This saved run has no current trace.';
  $('rco-wave-probe').textContent=`${voltage}${current} RC0 is ${direction} at ${slope.toFixed(3)} V/µs. ${near?`RC0 is near the ${threshold.toFixed(2)} V half-supply reference; inspect whether the next stage flips here.`:`RC0 is ${row[1]<threshold?'below':'above'} the ${threshold.toFixed(2)} V half-supply reference.`} The exact inverter trip point is model-dependent. A capacitor's current follows C × dV/dt; supply draw also includes other devices.`;
  drawRcoPlot();drawRcoCurrent();
}
function rcoSelectInterval(index){
  if(state.rcoIntervalStart==null||state.rcoIntervalEnd!=null){state.rcoIntervalStart=index;state.rcoIntervalEnd=null;$('rco-wave-interval').textContent=`Start at ${state.rco.samples[index][0].toFixed(3)} µs. Click a later or earlier time for the end.`;}
  else{state.rcoIntervalEnd=index;const rows=state.rco.samples,a=Math.min(index,state.rcoIntervalStart),b=Math.max(index,state.rcoIntervalStart),dt=rows[b][0]-rows[a][0];if(dt<=0){$('rco-wave-interval').textContent='Choose two different times.';}else{let energy=0;for(let i=a+1;i<=b;i++)if(rows[i].length>5)energy+=(rows[i-1][5]+rows[i][5])/2*(rows[i][0]-rows[i-1][0])*1e-6*state.rco.selected.supply_v;const dv=rows[b][1]-rows[a][1],current=rows[a].length>5?` · mean supply draw ${(energy/(dt*1e-6)/state.rco.selected.supply_v*1e6).toFixed(2)} µA · energy ${(energy*1e12).toFixed(3)} pJ`:'';$('rco-wave-interval').textContent=`${rows[a][0].toFixed(3)}–${rows[b][0].toFixed(3)} µs · Δt ${dt.toFixed(3)} µs · RC0 ΔV ${dv.toFixed(3)} V · average RC0 slope ${(dv/dt).toFixed(3)} V/µs${current}. Energy uses a trapezoidal estimate from the displayed supply-current samples.`;}}
  inspectRcoWave(index);
}
function analyzeRcoRange(){
  const rows=state.rco?.samples;if(!rows?.length)return;
  const col=Number($('rco-range-signal').value),current=col===5,unit=current?'µA':'V',signal=current?'supply current':col===4?'CLK_OUT':`RC${col-1}`;
  if(current&&rows[0].length<6){$('rco-range-result').textContent='This saved run has no supply-current trace. Run the current testbench to record it.';return;}
  const rawMin=$('rco-range-min').value,rawMax=$('rco-range-max').value,min=rawMin===''?-Infinity:Number(rawMin),max=rawMax===''?Infinity:Number(rawMax),start=Number($('rco-range-start').value),end=Number($('rco-range-end').value);
  if(!Number.isFinite(start)||!Number.isFinite(end)||start>=end||min>max){$('rco-range-result').textContent='Enter a time window with start < end and a signal band with minimum ≤ maximum.';return;}
  const value=row=>row[col]*(current?1e6:1);
  let observed=0,inside=0,weighted=0,longest=0,streak=0,entries=0,previousInside=false;
  for(let i=1;i<rows.length;i++){
    const left=Math.max(start,rows[i-1][0]),right=Math.min(end,rows[i][0]);if(right<=left)continue;
    const dt=right-left,middle=(value(rows[i-1])+value(rows[i]))/2,hit=middle>=min&&middle<=max;
    observed+=dt;if(hit){inside+=dt;weighted+=middle*dt;streak+=dt;if(!previousInside)entries++;longest=Math.max(longest,streak);}else streak=0;
    previousInside=hit;
  }
  if(!observed){$('rco-range-result').textContent='That time window does not overlap the displayed late-cycle trace.';return;}
  const band=`${rawMin===''?'−∞':Number(min).toFixed(3)} to ${rawMax===''?'∞':Number(max).toFixed(3)} ${unit}`;
  let lesson=current?'Supply-current peaks can mark capacitors charging, output switching, or both MOS devices conducting briefly. Align a peak with the voltage traces; the current plot alone does not identify its device.':`A voltage near ${ (state.rco.selected.supply_v/2).toFixed(2)} V is near a useful half-supply reference for an inverter transition. The actual trip point may differ.`;
  if(current&&min<=0&&max>=0)lesson='Near-zero supply current means little is being drawn from VDD at that moment; other current paths and leakage may still exist.';
  $('rco-range-result').textContent=`In ${start.toFixed(3)}–${end.toFixed(3)} µs, ${signal} was in ${band} for about ${inside.toFixed(3)} µs of ${observed.toFixed(3)} µs (${(100*inside/observed).toFixed(1)}%). ${entries} entries into the band; longest continuous displayed stretch ${longest.toFixed(3)} µs.${inside?` Mean value while inside: ${(weighted/inside).toFixed(3)} ${unit}.`:''} ${lesson} Estimates use the displayed sampled trace.`;
}
function rcoHighCurrentBand(){const values=(state.rco?.samples||[]).filter(row=>row.length>5).map(row=>row[5]*1e6).sort((a,b)=>a-b);if(!values.length)return;return values[Math.floor(.9*(values.length-1))].toFixed(1);}
function rcoTrimCodeAt(event){const rect=event.currentTarget.getBoundingClientRect();return Math.max(0,Math.min(511,Math.round((event.clientX-rect.left-55)/(rect.width-73)*511)));}
function drawRcoTrim(){
  if(state.view!=='rco')return;const canvas=$('rco-trim-canvas'),{ctx,w,h}=canvasSetup(canvas),data=state.rco?.full_trim,pad={l:55,r:18,t:20,b:36};ctx.fillStyle='#091c27';ctx.fillRect(0,0,w,h);
  if(!data){const codes=new Set((state.rco?.runs||[]).filter(run=>run.passives==='pdk'&&run.bank_style===state.rco?.selected?.bank_style&&run.main).map(run=>run.code));ctx.fillStyle='#91afbb';ctx.font='12px ui-sans-serif,sans-serif';ctx.fillText(`${codes.size} distinct nominal trim codes have saved Mac runs.`,18,43);$('rco-full-trim-status').textContent=`${codes.size}/512 codes recorded · full report pending`;$('rco-full-trim-scope').textContent='The graph appears after a completed, hash-checked 512-code native Mac sweep. Saved runs can include earlier experiments; this count alone is not a completed sweep. The AC bank map below is separate.';return;}
  const points=data.points,frequencies=points.map(item=>item[1]/1000),lo=Math.min(...frequencies,512)*.96,hi=Math.max(...frequencies,512)*1.04,x=code=>pad.l+code/511*(w-pad.l-pad.r),y=f=>h-pad.b-(f-lo)/(hi-lo)*(h-pad.t-pad.b);
  ctx.strokeStyle='#294b58';ctx.fillStyle='#91afbb';ctx.lineWidth=1;ctx.font='11px ui-monospace,monospace';for(let i=0;i<=4;i++){const xx=pad.l+i*(w-pad.l-pad.r)/4,yy=pad.t+i*(h-pad.t-pad.b)/4;ctx.beginPath();ctx.moveTo(xx,pad.t);ctx.lineTo(xx,h-pad.b);ctx.moveTo(pad.l,yy);ctx.lineTo(w-pad.r,yy);ctx.stroke();ctx.fillText(String(Math.round(511*i/4)),xx-10,h-11);ctx.fillText((hi-(hi-lo)*i/4).toFixed(0),4,yy+4);}
  ctx.fillText('kHz',5,13);ctx.beginPath();ctx.strokeStyle='#d9d06e';ctx.setLineDash([5,4]);ctx.moveTo(pad.l,y(512));ctx.lineTo(w-pad.r,y(512));ctx.stroke();ctx.setLineDash([]);
  ctx.beginPath();ctx.strokeStyle='#5ad9e9';ctx.lineWidth=1.5;points.forEach(([code,f],i)=>i?ctx.lineTo(x(code),y(f/1000)):ctx.moveTo(x(code),y(f/1000)));ctx.stroke();ctx.strokeStyle='#ff8b83';ctx.lineWidth=3;for(const step of data.reversed_steps){const a=points[step.from],b=points[step.to];ctx.beginPath();ctx.moveTo(x(a[0]),y(a[1]/1000));ctx.lineTo(x(b[0]),y(b[1]/1000));ctx.stroke();}
  $('rco-full-trim-status').textContent=`512 Mac transient runs · ${data.reversed_steps.length} reversed steps · closest code ${data.best.code}`;$('rco-full-trim-scope').textContent=data.scope+' Red segments are frequency increases when code increases; click the graph to put that code in the testbench.';
}
function rcoCapWindow(){const selected=Math.max(0,Math.min(511,Number($('rco-code').value)||0));if($('rco-cap-range').value==='full')return [0,511];const first=Math.max(0,Math.min(495,selected-8));return [first,first+16];}
function rcoCapCodeAt(clientX,canvas){const [first,last]=rcoCapWindow(),box=canvas.getBoundingClientRect();return Math.max(first,Math.min(last,Math.round(first+(clientX-box.left-58)/(box.width-76)*(last-first))));}
function drawRcoCapPlot(){
  if(state.view!=='rco')return;
  const canvas=$('rco-cap-canvas'),{ctx,w,h}=canvasSetup(canvas),pad={l:58,r:18,t:20,b:38};
  ctx.fillStyle='#091c27';ctx.fillRect(0,0,w,h);
  const data=state.rco?.bank_ac,rows=data?.points;
  if(!rows?.length){ctx.fillStyle='#91afbb';ctx.font='13px ui-sans-serif,sans-serif';ctx.fillText('No 512-code AC bank sweep recorded for this process and bank style.',24,45);return;}
  const [first,last]=rcoCapWindow(),shown=rows.slice(first,last+1),values=shown.map(row=>row[1]),span=Math.max(1,Math.max(...values)-Math.min(...values)),lo=Math.min(...values)-span*.08,hi=Math.max(...values)+span*.08;
  const x=code=>pad.l+(code-first)/(last-first)*(w-pad.l-pad.r),y=cap=>h-pad.b-(cap-lo)/(hi-lo)*(h-pad.t-pad.b);
  ctx.strokeStyle='#294b58';ctx.fillStyle='#91afbb';ctx.lineWidth=1;ctx.font='11px ui-monospace,monospace';
  for(let i=0;i<=4;i++){const xx=pad.l+i*(w-pad.l-pad.r)/4;ctx.beginPath();ctx.moveTo(xx,pad.t);ctx.lineTo(xx,h-pad.b);ctx.stroke();ctx.fillText(String(Math.round(first+(last-first)*i/4)),xx-12,h-12);const yy=pad.t+i*(h-pad.t-pad.b)/4;ctx.beginPath();ctx.moveTo(pad.l,yy);ctx.lineTo(w-pad.r,yy);ctx.stroke();ctx.fillText((hi-(hi-lo)*i/4).toFixed(0),5,yy+4);}
  ctx.save();ctx.beginPath();ctx.rect(pad.l,pad.t,w-pad.l-pad.r,h-pad.t-pad.b);ctx.clip();
  ctx.beginPath();ctx.strokeStyle='#5ad9e9';ctx.lineWidth=1.7;shown.forEach(([code,cap],i)=>i?ctx.lineTo(x(code),y(cap)):ctx.moveTo(x(code),y(cap)));ctx.stroke();
  ctx.strokeStyle='#ff8b83';ctx.lineWidth=3;for(const step of data.reversed_steps){if(step.from<first||step.to>last)continue;const a=rows[step.from],b=rows[step.to];ctx.beginPath();ctx.moveTo(x(a[0]),y(a[1]));ctx.lineTo(x(b[0]),y(b[1]));ctx.stroke();}
  const selected=Number($('rco-code').value);if(Number.isInteger(selected)&&rows[selected]&&selected>=first&&selected<=last){ctx.beginPath();ctx.fillStyle='#ffd17d';ctx.arc(x(selected),y(rows[selected][1]),4,0,Math.PI*2);ctx.fill();}
  ctx.restore();
}
const rcoPlacementHits={sky130:[],gf180:[]};
function rcoPlacementIds(process){return process==='sky130'?['rco-placement-sky','rco-placement-sky-region','rco-placement-sky-status','rco-placement-sky-detail']:['rco-placement-gf','rco-placement-gf-region','rco-placement-gf-status','rco-placement-gf-detail'];}
function drawRcoPlacement(process){
  if(state.view!=='rco')return;
  const [canvasId,regionId,statusId]=rcoPlacementIds(process),canvas=$(canvasId),{ctx,w,h}=canvasSetup(canvas),placement=state.rco?.placements?.[process];
  ctx.fillStyle='#091c27';ctx.fillRect(0,0,w,h);rcoPlacementHits[process]=[];
  if(!placement){$(statusId).textContent='No hashed, DRC-clear placement recorded.';return;}
  $(statusId).textContent=`${placement.instances.length} PDK devices · Magic DRC ${placement.magic_drc_errors} · KLayout DRC ${placement.klayout_drc_items} · GDS ${placement.gds_sha256.slice(0,12)}…`;
  const region=$(regionId).value,entries=placement.instances.filter(item=>region==='all'||(region==='mos'?(item.kind==='nmos'||item.kind==='pmos'):(item.kind==='cap'||item.kind==='res')));
  if(!entries.length)return;
  const xs=entries.map(item=>item.origin_um[0]),ys=entries.map(item=>item.origin_um[1]),xmin=Math.min(...xs)-15,xmax=Math.max(...xs)+20,ymin=Math.min(...ys)-15,ymax=Math.max(...ys)+20;
  const pad={l:30,r:18,t:28,b:22},scale=Math.min((w-pad.l-pad.r)/(xmax-xmin),(h-pad.t-pad.b)/(ymax-ymin));
  const x=value=>pad.l+(value-xmin)*scale,y=value=>h-pad.b-(value-ymin)*scale;
  ctx.strokeStyle='#284956';ctx.lineWidth=1;for(let i=0;i<3;i++){const xx=x(105+i*340);ctx.beginPath();ctx.moveTo(xx,pad.t);ctx.lineTo(xx,h-pad.b);ctx.stroke();}
  ctx.fillStyle='#9ab4be';ctx.font='11px ui-sans-serif,sans-serif';ctx.fillText(region==='mos'?'MOS devices, controls, and output buffers':'Three RC banks and their delay resistors',12,16);
  for(const item of entries){const px=x(item.origin_um[0]),py=y(item.origin_um[1]);ctx.fillStyle=item.kind==='cap'?'#5ad9e9':item.kind==='res'?'#f6b76a':item.kind==='pmos'?'#d4a6ff':'#98e4a7';
    if(item.kind==='res')ctx.fillRect(px-2,py-9,4,18);else if(item.kind==='cap')ctx.fillRect(px-2.5,py-2.5,5,5);else{ctx.beginPath();ctx.arc(px,py,3,0,2*Math.PI);ctx.fill();}
    rcoPlacementHits[process].push({item,x:px,y:py});}
}
function inspectRcoPlacement(process,event){
  const [canvasId,,,detailId]=rcoPlacementIds(process),box=$(canvasId).getBoundingClientRect(),px=event.clientX-box.left,py=event.clientY-box.top;
  const hit=rcoPlacementHits[process].map(entry=>({...entry,d:Math.hypot(entry.x-px,entry.y-py)})).sort((a,b)=>a.d-b.d)[0];
  if(!hit||hit.d>16)return;
  const item=hit.item,physics=item.kind==='cap'?'Its plate area sets much of its capacitance. Extra wire and fringe capacitance change the RC delay and can disturb trim steps.':item.kind==='res'?'Its poly length sets nominal resistance. Gradient, contacts, temperature, and routing add error to the delay.':item.kind==='pmos'?'The PMOS conducts as its gate falls. Well proximity, body tie, and source/drain access affect its switching and resistance.':'The NMOS conducts as its gate rises. Substrate tie, stress, and source/drain access affect its switching and resistance.';
  const params=Object.entries(item.parameters).map(([key,value])=>`${key}=${value}`).join(', ');
  $(detailId).textContent=`${item.name} · ${item.kind.toUpperCase()} · ${params} · origin (${item.origin_um[0]}, ${item.origin_um[1]}) µm. Schematic terminals: ${item.nets_from_schematic.join(' / ')}. ${physics} These terminals are not routed. This GDS cell is static; change the circuit source or placement generator, then regenerate and recheck it.`;
}
function renderRcoFactors(){
  const placement=state.rco?.placements?.[state.process],target=$('rco-layout-factors');clear(target);
  if(!placement){add(target,'div','No validated placement spans are available.');return;}
  const nodes=['n0','n1','n2'].map(net=>{const item=placement.net_spans[net];return `${net}: ${item.width_um} × ${item.height_um} µm across ${item.instances} device origins`;}).join(' · ');
  for(const [title,body] of [
    ['1 · RC node spread',`${nodes}. These wide placement spans are a warning that connecting the stages and banks could add substantial wire resistance and capacitance. Rwire ≈ ρL/(width × thickness); added C makes the RC input reach the inverter threshold later. Re-place the related devices closer before routing.`],
    ['2 · Capacitor-bank accuracy',`${placement.counts.cap} MIM cells serve three banks. Each trim bit is an effective series/parallel combination, so edge position, neighboring metal, via access, and mismatched switch routing can change its effective capacitance. Around binary carries, the new high bit must outweigh all lower bits; a fixed-bias AC map cannot prove transient monotonicity after layout.`],
    ['3 · MOS, well, and body',`The placement has ${placement.counts.nmos} NMOS and ${placement.counts.pmos} PMOS devices. Source/drain diffusion and gate access add delay and parasitic C. GF local taps passed spacing rules, but their metal is not tied to VDD/VSS; SKY gate contacts also require legal routing. Well proximity, STI stress, and device orientation can shift transistor behavior and matching.`],
    ['4 · Power and switching',`The output buffers and control shifters draw current in addition to the capacitor banks. Rough dynamic power follows α C VDD² f, while slow RC-driven inputs can create PMOS/NMOS overlap current. A routed power network can add voltage drop and ground bounce. Compare current pulses with CLK transitions, then use post-layout PEX to locate the added R and C.${state.process==='sky130'?' The SKY130 RCX documentation says coupling from nearby routing to precision resistors is not extracted; keep other wiring away from those resistors and treat that omission as a modeling limit.':''}`]
  ]){const card=add(target,'div');add(card,'strong',title);add(card,'p',body);}
}
function renderRcoCorners(){
  const data=state.rco?.corner_trim,target=$('rco-corner-results');clear(target);
  if(!data){add(target,'div','No completed process-corner trim search has been recorded for this PDK.');$('rco-corner-scope').textContent='The nominal waveform above is a typical-corner result. Corner searches use separate PDK model sections and save separate hashed netlists, logs, and waveforms.';return;}
  for(const [name,item] of Object.entries(data.scenarios)){
    const card=add(target,'div');add(card,'strong',name==='fast_cold_high_v'?'Fast silicon · cold · high supply':'Slow silicon · hot · low supply');
    add(card,'p',`PDK section ${item.model_corner}, ${item.temperature_c} °C, VDD ${item.supply_v.toFixed(3)} V. Best sampled code ${item.best_code}: ${(item.best_frequency_hz/1000).toFixed(3)} kHz (${item.best_error_pct>=0?'+':''}${item.best_error_pct.toFixed(3)}%). ${item.sampled.length} codes measured. ${item.endpoint_bracketed?'Target lies between measured endpoint frequencies.':'Measured endpoint frequencies do not bracket the target.'}`);
  }
  $('rco-corner-scope').textContent=data.scope+' Binary-search sampling can miss a better code when trim steps reverse; it does not prove all 512 codes.';
}
function renderRco(){
  const d=state.rco,select=$('rco-run-select');clear(select);
  if(!d?.selected){$('rco-run-status').textContent='No RCO simulation recorded for this process.';$('rco-scope').textContent=d?.scope||'';return;}
  for(const item of d.runs){const option=add(select,'option',rcoRunLabel(item));option.value=item.id;}
  select.value=d.selected.id;state.rcoRun=d.selected.id;
  $('rco-code').value=d.selected.code;$('rco-main').checked=d.selected.main;$('rco-passives').value=d.selected.passives==='pdk_legacy'?'pdk':d.selected.passives;$('rco-bank-style').value=d.selected.bank_style;$('rco-xschem').checked=d.selected.schematic==='xschem';
  $('rco-run-status').textContent=`Saved Mac simulation ${d.selected.id.slice(0,8)}`;
  const grid=$('rco-metrics');clear(grid);
  const readings=[['Target','512.000 kHz'],['Measured',`${(d.selected.frequency_hz/1000).toFixed(3)} kHz`],['Error',`${d.selected.frequency_error_pct>=0?'+':''}${d.selected.frequency_error_pct.toFixed(3)}%`],['Oscillator supply',`${d.selected.supply_v.toFixed(1)} V`],['Control level',`${d.selected.control_v.toFixed(1)} V`],['Output swing',`${d.selected.vlow_v.toFixed(3)}–${d.selected.vhigh_v.toFixed(3)} V`]];
  if(d.selected.duty_cycle_pct!=null)readings.push(['Clock duty',`${d.selected.duty_cycle_pct.toFixed(2)}%`]);
  if(d.selected.core_supply_power_w!=null)readings.push(['Core supply power',`${(d.selected.core_supply_power_w*1e6).toFixed(2)} µW`]);
  for(const [label,value] of readings){const row=add(grid,'div',undefined,'detail');add(row,'div',label,'label');add(row,'div',value,'value');}
  $('rco-scope').textContent=d.scope;
  $('rco-wave-source').textContent=`${d.selected.ngspice_version} · ${d.samples.length.toLocaleString()} samples · schematic-level PDK simulation, no RCO PEX`;
  state.rcoProbe=null;state.rcoIntervalStart=null;state.rcoIntervalEnd=null;
  $('rco-wave-probe').textContent='Move over a waveform to inspect voltage, slope, threshold, and current.';
  $('rco-wave-interval').textContent='Select two times to measure an interval.';
  $('rco-range-start').value=d.samples[0][0].toFixed(3);$('rco-range-end').value=d.samples[d.samples.length-1][0].toFixed(3);
  if($('rco-range-signal').value==='5'){$('rco-range-min').value=rcoHighCurrentBand()||'';$('rco-range-max').value='';}else{$('rco-range-min').value=(d.selected.supply_v*.45).toFixed(3);$('rco-range-max').value=(d.selected.supply_v*.55).toFixed(3);}
  $('rco-range-result').textContent='Choose a signal band, then press Explain this range.';
  $('rco-run-path').textContent=`${d.run_path}/rco.spice · SHA-256 ${d.selected.netlist_sha256.slice(0,16)}… · waveform ${d.selected.waveform_sha256?.slice(0,16)||'hash not recorded'} · PDK models ${d.selected.model_tree_sha256.slice(0,16)}…${d.selected.schematic_sha256?` · Xschem source ${d.selected.schematic_sha256.slice(0,16)}…`:''}`;
  $('rco-schematic-path').textContent=d.schematic_source;
  const probe=d.passive_probe;
  $('rco-open-passive-probe').disabled=!probe;
  $('rco-passive-probe').textContent=probe?`Isolated cell: Magic DRC ${probe.magic_drc_errors} errors; native KLayout DRC ${probe.klayout_drc_items} items. Extracted: ${probe.models.join(' · ')}. GDS SHA-256 ${probe.gds_sha256.slice(0,16)}…`:'No passive-device GDS check recorded for this process.';
  const byCode=new Map();for(const item of d.runs){if(item.passives==='pdk'&&item.main&&item.bank_style===d.selected.bank_style&&!byCode.has(item.code))byCode.set(item.code,item);}
  const trimPoints=[...byCode.values()].sort((a,b)=>a.code-b.code),adjacent=[],reversed=[];
  for(let i=1;i<trimPoints.length;i++){const a=trimPoints[i-1],b=trimPoints[i];if(b.code!==a.code+1)continue;adjacent.push([a,b]);if(b.frequency_hz>=a.frequency_hz)reversed.push([a,b]);}
  const fullSteps=d.full_trim?.reversed_steps,stepCount=d.full_trim?511:adjacent.length,reverseCount=d.full_trim?fullSteps.length:reversed.length;
  $('rco-trim-check').textContent=stepCount?`${stepCount} measured adjacent pairs; ${reverseCount} run opposite to the expected lower-frequency direction.${reverseCount?` Reversals: ${d.full_trim?fullSteps.slice(0,8).map(step=>`${step.from}→${step.to}`).join(', '):reversed.slice(0,8).map(([a,b])=>`${a.code}→${b.code}: ${(a.frequency_hz/1000).toFixed(3)}→${(b.frequency_hz/1000).toFixed(3)} kHz`).join(' · ')}${reverseCount>8?` · ${reverseCount-8} more`:''}.`:''}`:'No adjacent current-PDK trim codes have been measured yet.';
  $('rco-trim-scope').textContent=d.full_trim?'All 511 adjacent code pairs come from the completed, hash-checked native Mac nominal transient sweep. Corner and post-layout monotonicity remain untested.':'Only adjacent code pairs with saved current-PDK passive runs are compared. This is not a full 512-code monotonicity check.';
  renderRcoCorners();
  $('rco-cap-scope').textContent=d.bank_ac?`${d.bank_ac.scope} ${d.bank_ac.reversed_steps.length} of 511 AC capacitance steps reverse direction. Click the graph to load a code; run a transient separately.`:'No complete 512-code AC sweep recorded for this process and selected bank style.';
  $('rco-cap-hover').textContent=d.bank_ac?`512 codes · ${d.bank_ac.reversed_steps.length} reversed AC steps`:'AC sweep pending';
  $('rco-netlist').textContent=d.netlist;
  const log=$('rco-design-log');clear(log);
  const baseline=d.runs.find(item=>item.code===100&&item.main&&item.passives==='ideal'),near=d.runs.find(item=>item.code===(state.process==='sky130'?164:137)&&item.main&&item.passives==='ideal'),off=d.runs.find(item=>!item.main&&item.passives===d.selected.passives&&item.bank_style===d.selected.bank_style);
  analysisCard(log,'1 · Choose the loop',`Three CMOS inversions make a ring. At 512 kHz, its average stage delay needs to be about 1/(6 × 512 kHz) = 325.5 ns. A 470 kΩ resistor and roughly 1 pF node capacitance are a starting estimate.`);
  analysisCard(log,'2 · Start from an RC estimate',`Code 100 gives 1.0 pF of ideal base-plus-bank capacitance per stage. ${baseline?`The ideal-passive simulation measured ${(baseline.frequency_hz/1000).toFixed(1)} kHz.`:'The first code-100 ideal-passive simulation has not been saved for this process.'} The formula omits switch and transistor behavior.`);
  analysisCard(log,'3 · Add switched capacitance',`${near?`Code ${near.code} measured ${(near.frequency_hz/1000).toFixed(1)} kHz.`:'A near-target bank code has not been recorded.'} More capacitance slows the RC crossing at each inverter input. The selected code ${d.selected.code} measures ${(d.selected.frequency_hz/1000).toFixed(3)} kHz on ${state.overview.processes[state.process].title}.`);
  analysisCard(log,'4 · Check the main PMOS/NMOS gate',`${off?`With the bank disconnected, the recorded frequency is ${(off.frequency_hz/1000).toFixed(1)} kHz.`:'The master-switch-off control has not been tested.'} This tests bank selection; the gate does not adjust the inverter voltage threshold.`);
  analysisCard(log,'5 · Make the bank manufacturable',`A single 5 fF MIM cell violates GF180's 5 × 5 µm minimum. The PDK variant uses 5 × 5 µm GF option-B 2 fF/µm² or 4.5 × 4.5 µm SKY unit cells. Series chains make the small weights; parallel units make the larger weights. Each SKY stage uses 77 units plus a base MIM; GF uses 61 units plus a base MIM. The two banks need different trim codes.`);
  analysisCard(log,'6 · Compare passive models',`The selected run uses ${d.selected.passives==='pdk'?'PDK high-resistance poly and MIM models':'ideal 470 kΩ resistors and binary capacitors'} with ${d.selected.bank_style} bank weights. Code ${d.selected.code} measures ${(d.selected.frequency_hz/1000).toFixed(3)} kHz. SKY130A and GF180MCU D need separate calibration because their device values and switch delays differ.`);
  analysisCard(log,'7 · Check binary carry transitions',`${stepCount} adjacent pairs have been measured for the selected bank; ${reverseCount} reversed frequency direction.${reverseCount?` Observed: ${d.full_trim?fullSteps.map(step=>`${step.from}→${step.to}`).join(', '):reversed.map(([a,b])=>`${a.code}→${b.code}`).join(', ')}.`:''} ${d.selected.bank_style==='balanced'?`The balanced GF bank has ${d.bank_ac?.reversed_steps.length??'no recorded full count of'} reversed steps in its 512-code AC map. ${d.full_trim?'The nominal 512-code transient sweep is recorded; the corner searches sample a trim path rather than all codes.':'The nominal 512-code transient sweep is running; corner searches sample a trim path rather than all codes.'}`:state.process==='gf180'?'The progressive guard experiment has 112 reversed AC steps and a 37.6 kHz transient gap at 127→128, so it is not the calibrated baseline.':d.full_trim?'The nominal 512-code transient sweep is recorded; review its reversal count in the graph.':'A full SKY trim sweep is running to assess nominal monotonicity.'}`);
  analysisCard(log,'8 · Audit the passive cells',probe?'Isolated PDK MIM and high resistance poly cells were drawn and extracted. Both Magic and native KLayout reported zero DRC items for these test cells; this is not full RCO verification.':'No isolated passive-device GDS check has been recorded.');
  analysisCard(log,'9 · Inspect the placement','Both PDKs have a PDK-device placement and zero Magic and native KLayout DRC markers for that unrouted geometry. The 130 MOS devices, three resistors, and 234 SKY or 186 GF MIMs still need connecting wires, body ties, LVS, PEX, and charge-state checks. Sampled schematic corner searches are recorded separately.');
  renderRcoFactors();
  requestAnimationFrame(()=>{drawRcoPlot();drawRcoCurrent();drawRcoTrim();drawRcoCapPlot();drawRcoPlacement('sky130');drawRcoPlacement('gf180');});
}
async function loadRco(runId=null){
  const process=state.process;$('rco-run-status').textContent='Reading hashed Mac simulation…';
  const data=await api(query('/api/rco',{process,...(runId?{run:runId}:{})}));
  if(process!==state.process||state.view!=='rco')return;
  state.rco=data;renderRco();
}
async function simulateRco(){
  const code=Number($('rco-code').value),main=$('rco-main').checked,passives=$('rco-passives').value,bank_style=$('rco-bank-style').value,schematic=$('rco-xschem').checked?'xschem':'generated',process=state.process,button=$('rco-run-button');
  if(!Number.isInteger(code)||code<0||code>511){notice('Choose an integer trimmer code from 0 to 511.',true);return;}
  button.disabled=true;$('rco-run-status').textContent='Running native Mac ngspice with the selected PDK model…';
  try{
    const data=await api('/api/rco-simulate',{method:'POST',headers:{'Content-Type':'application/json','X-Lab-Token':state.overview.token},body:JSON.stringify({process,code,main,passives,schematic,bank_style})});
    while(true){await new Promise(resolve=>setTimeout(resolve,2000));const job=await api(query('/api/job',{id:data.job_id}));if(job.state==='running')continue;
      if(job.state==='complete'){if(process===state.process&&state.view==='rco')await loadRco(job.run_id);notice(`RCO code ${code} measured and saved as ${job.run_id.slice(0,8)}.`);}
      else throw new Error(job.output||'RCO simulation failed');break;}
  }catch(err){$('rco-run-status').textContent='Simulation failed';notice(err.message,true);}finally{button.disabled=false;}
}
function setView(view){state.view=view;state.circuit=view==='rco'?'rco':'inverter';$('circuit-select').value=state.circuit;$('inverter-run-control').hidden=state.circuit==='rco';for(const el of document.querySelectorAll('.view'))el.classList.toggle('active',el.id===`view-${view}`);for(const el of document.querySelectorAll('.nav-item'))el.classList.toggle('active',el.dataset.view===view);$('view-crumb').textContent=view==='rco'?'CIRCUIT LIBRARY':view.toUpperCase();if(view==='rco')loadRco().catch(err=>notice(err.message,true));if(view==='waveforms')loadWave().catch(err=>notice(err.message,true));if(view==='layout')loadLayout().catch(err=>notice(err.message,true));if(view==='verification')loadEvidence().catch(err=>notice(err.message,true));if(view==='pex')loadPex().catch(err=>notice(err.message,true));if(view==='schematic'){loadSchematic().catch(err=>notice(err.message,true));if(state.editorExperiment)requestAnimationFrame(()=>drawPlot($('schematic-canvas'),state.editorExperiment.samples));}if(view==='documents'&&!state.doc)loadDoc(state.overview.documents[0]).catch(err=>notice(err.message,true));if(view==='experiments'&&state.experiment)requestAnimationFrame(()=>drawPlot($('experiment-canvas'),state.experiment.samples));}
async function loadTestbench(){
  if(!state.report)return;
  const process=state.process,run=state.run,kind=$('testbench-select').value;
  const name=kind==='rcx'?(process==='gf180'?'connected/rcx/postlayout_rcx.spice':'rcx/postlayout_rcx.spice'):kind==='postlayout'?(process==='gf180'?'connected/postlayout.spice':'postlayout.spice'):'inverter.spice';
  const folder=process==='gf180'?'gf180_inverter':'sky130_inverter';
  $('testbench-path').textContent=`${state.report.local_path||`runs/${folder}/${run}`}/${name}`;
  $('testbench-code').textContent='Loading exact run artifact…';
  if(!state.report.artifacts?.includes(name)){$('testbench-summary').textContent='This testbench is not recorded in the selected run.';$('testbench-code').textContent='';return;}
  const result=await api(query('/api/artifact',{process,run,name}));
  if(state.process!==process||state.run!==run||$('testbench-select').value!==kind)return;
  $('testbench-code').textContent=result.text;
  const hash=state.report.evidence_sha256?.[name]?.slice(0,16)||'unrecorded';
  $('testbench-summary').textContent=kind==='rcx'?`Distributed R-C deck · explicit wire resistors · SHA-256 ${hash}…`:kind==='postlayout'?`Capacitance-only deck · extracted inverter included · SHA-256 ${hash}…`:`Schematic deck · same stimulus and 5 fF load · SHA-256 ${hash}…`;
}
async function loadWave(){
  if(!state.report)return;
  const process=state.process,run=state.run,kind=state.waveKind;
  $('wave-source').textContent='Generating trace from the selected run…';
  $('testbench-select').value=kind;
  loadTestbench().catch(err=>notice(err.message,true));
  let data;
  try{data=await api(query('/api/waveform',{process,run,kind}));}
  catch(err){$('wave-source').textContent=`Waveform unavailable: ${err.message}`;throw err;}
  if(process!==state.process||run!==state.run||kind!==state.waveKind)return;
  state.wave=data;
  $('wave-source').textContent=`${data.source} · ${data.samples.length.toLocaleString()} points · source ${data.run_id.slice(0,8)}`;
  requestAnimationFrame(()=>drawPlot($('wave-canvas'),data.samples,state.waveSignals));
  const stats=metric(state.report.checks,kind),box=$('wave-metrics');clear(box);
  for(const [label,value] of [['tPHL',fmtPs(stats?.tphl)],['tPLH',fmtPs(stats?.tplh)],['VOUT high',stats?.vout_high==null?'—':`${Number(stats.vout_high).toFixed(3)} V`],['VOUT low',stats?.vout_low==null?'—':`${Number(stats.vout_low).toExponential(2)} V`]]){const card=add(box,'div',undefined,'detail');add(card,'div',label,'label');add(card,'div',value,'value');}
  loadAnalysis();
}
function analysisMessage(message){for(const id of ['wave-analysis','layout-analysis','pex-analysis'])$(id).textContent=message;}
function analysisCard(parent,title,body){const card=add(parent,'div',undefined,'analysis-card');add(card,'strong',title);add(card,'p',body);}
function renderAnalysis(){
  const d=state.analysis;if(!d)return;
  const wave=$('wave-analysis');clear(wave);
  const table=add(wave,'div',undefined,'analysis-table');
  for(const row of [['Trace','tPHL','tPLH','Fall 90–10%','Rise 10–90%'],...d.waveforms.map(item=>[
    {schematic:'Schematic',postlayout:'C only',rcx:'Distributed R-C'}[item.kind],
    `${item.tphl_ps.toFixed(2)} ps`,`${item.tplh_ps.toFixed(2)} ps`,
    `${item.fall_90_10_ps.toFixed(2)} ps`,`${item.rise_10_90_ps.toFixed(2)} ps`])]){
    const line=add(table,'div',undefined,'analysis-row');for(const value of row)add(line,'span',value);
  }
  const delta=d.deltas_ps;
  analysisCard(wave,'Added delay in this run',`C only versus schematic: +${delta.tphl_ps.c_only_minus_schematic.toFixed(2)} ps falling, +${delta.tplh_ps.c_only_minus_schematic.toFixed(2)} ps rising. Distributed R-C versus C only: +${delta.tphl_ps.rc_minus_c_only.toFixed(2)} / +${delta.tplh_ps.rc_minus_c_only.toFixed(2)} ps.`);
  analysisCard(wave,'What the traces say',`The extracted output transitions are slower than the schematic transitions. The 5 fF external output load is present in all three tests. The additional extracted network and device geometry account for the difference; R-C minus C-only cannot isolate resistance because the extraction topology also changes.`);
  const layout=$('layout-analysis');clear(layout);
  const geometry=state.process==='gf180'
    ?'The two transistor gates are joined by a continuous polysilicon stripe. Its length and gate contacts are plausible contributors to the IN-to-gate resistance; the extraction does not assign an ohmic value to a specific poly shape.'
    :'The metal2 IN and OUT buses span both transistor rows. Their area and proximity to other conductors plausibly contribute capacitance; the extracted network does not identify a capacitor plate or resistance layer.';
  analysisCard(layout,'Gate access',`IN to NMOS gate: ${d.terminal_ohm['NMOS gate'].toFixed(2)} Ω. IN to PMOS gate: ${d.terminal_ohm['PMOS gate'].toFixed(2)} Ω. ${geometry}`);
  analysisCard(layout,'Capacitor connections',`The top-level R-C netlist has ${d.incident_cap_ff.IN.toFixed(3)} fF touching IN and ${d.incident_cap_ff.OUT.toFixed(3)} fF touching OUT. Its largest elements are ${d.largest_capacitors.slice(0,3).map(item=>`${item.id} ${item.a}–${item.b} ${item.ff.toFixed(3)} fF`).join('; ')}. VDD–VSS capacitance couples supply rails; it is not an output load by itself.`);
  if(d.reference){const r=d.reference;analysisCard(layout,'Measured layout revision',`Against the hashed reference ${r.run_id.slice(0,8)} with the same models, decks, testbench and worker: top-level C ${r.capacitance_change_ff.toFixed(3)} fF, PMOS gate path ${r.pmos_gate_resistance_change_ohm.toFixed(2)} Ω, R-C delay ${r.rc_tphl_change_ps.toFixed(2)} / ${r.rc_tplh_change_ps.toFixed(2)} ps (fall/rise). Negative means a reduction.`);}
  analysisCard(layout,'Limits',d.limits);
  const pex=$('pex-analysis');clear(pex);
  analysisCard(pex,'Measured transition penalty',`Relative to the schematic, the R-C result adds ${(d.waveforms[2].tphl_ps-d.waveforms[0].tphl_ps).toFixed(2)} ps to the falling delay and ${(d.waveforms[2].tplh_ps-d.waveforms[0].tplh_ps).toFixed(2)} ps to the rising delay. Output 90–10% fall and 10–90% rise times are ${d.waveforms[2].fall_90_10_ps.toFixed(2)} / ${d.waveforms[2].rise_10_90_ps.toFixed(2)} ps.`);
  if(d.reference)analysisCard(pex,'After the layout edit',`Compared with ${d.reference.run_id.slice(0,8)}, the validated R-C delays changed by ${d.reference.rc_tphl_change_ps.toFixed(2)} / ${d.reference.rc_tplh_change_ps.toFixed(2)} ps (fall/rise). Both runs used identical models, decks, stimulus and load; the selected layout source differs.`);
  analysisCard(pex,'Attribution',d.limits);
}
function loadAnalysis(){
  if(!state.report?.checks?.rc_network){analysisMessage('This run has no distributed R-C evidence.');return;}
  if(state.analysis){renderAnalysis();return;}
  if(state.analysisPromise)return;
  const process=state.process,run=state.run;analysisMessage('Measuring the three Mac ngspice traces and extracted network…');
  state.analysisPromise=api(query('/api/waveform-analysis',{process,run}))
    .then(data=>{if(process===state.process&&run===state.run){state.analysis=data;renderAnalysis();}})
    .catch(err=>{if(process===state.process&&run===state.run)analysisMessage(`Waveform analysis unavailable: ${err.message}`);})
    .finally(()=>{if(process===state.process&&run===state.run)state.analysisPromise=null;});
}
function canvasSetup(canvas){const rect=canvas.getBoundingClientRect(),dpr=window.devicePixelRatio||1;canvas.width=Math.max(1,Math.round(rect.width*dpr));canvas.height=Math.max(1,Math.round(rect.height*dpr));const ctx=canvas.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);return {ctx,w:rect.width,h:rect.height};}
function drawPlot(canvas,samples,signals=new Set(['in','out'])){
  if(!samples?.length)return;
  const {ctx,w,h}=canvasSetup(canvas),pad={l:54,r:24,t:22,b:38};
  ctx.clearRect(0,0,w,h);ctx.fillStyle='#0a1c27';ctx.fillRect(0,0,w,h);
  const x0=samples[0][0],x1=samples[samples.length-1][0];
  const y1=Math.max(...samples.map(row=>Math.max(row[1],row[2])))*1.1||1;
  const x=v=>pad.l+(v-x0)/(x1-x0)*(w-pad.l-pad.r),y=v=>h-pad.b-v/y1*(h-pad.t-pad.b);
  ctx.strokeStyle='#254453';ctx.lineWidth=1;ctx.fillStyle='#83a1ae';ctx.font='11px ui-monospace, monospace';
  for(let i=0;i<=6;i++){const xx=pad.l+i*(w-pad.l-pad.r)/6;ctx.beginPath();ctx.moveTo(xx,pad.t);ctx.lineTo(xx,h-pad.b);ctx.stroke();ctx.fillText((x0+(x1-x0)*i/6).toFixed(1),xx-12,h-14);}
  for(let i=0;i<=4;i++){const yy=pad.t+i*(h-pad.t-pad.b)/4;ctx.beginPath();ctx.moveTo(pad.l,yy);ctx.lineTo(w-pad.r,yy);ctx.stroke();ctx.fillText((y1*(1-i/4)).toFixed(1),8,yy+4);}
  ctx.save();ctx.beginPath();ctx.rect(pad.l,pad.t,w-pad.l-pad.r,h-pad.t-pad.b);ctx.clip();
  for(const [name,col,color] of [['in',1,'#5ad9e9'],['out',2,'#f6b76a']]){
    if(!signals.has(name))continue;
    ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();
    for(let i=0;i<samples.length;i++){const point=samples[i];if(i===0)ctx.moveTo(x(point[0]),y(point[col]));else ctx.lineTo(x(point[0]),y(point[col]));}
    ctx.stroke();
  }
  ctx.restore();
  if(!signals.size){ctx.fillStyle='#9ab7bf';ctx.font='12px ui-sans-serif,sans-serif';ctx.textAlign='center';ctx.fillText('Select V(IN) or V(OUT) to show a trace',w/2,h/2);ctx.textAlign='left';}
  canvas._plot={samples,pad,x0,x1,y1,signals:new Set(signals)};
}
function plotHover(event){
  const canvas=event.currentTarget,p=canvas._plot,tip=$('wave-tooltip');if(!p||!p.signals.size){tip.hidden=true;return;}
  const rect=canvas.getBoundingClientRect(),px=event.clientX-rect.left,time=p.x0+(px-p.pad.l)/(rect.width-p.pad.l-p.pad.r)*(p.x1-p.x0);
  if(px<p.pad.l||px>rect.width-p.pad.r){tip.hidden=true;return;}
  const index=Math.max(0,Math.min(p.samples.length-1,Math.round((time-p.x0)/(p.x1-p.x0)*(p.samples.length-1))));
  const row=p.samples[index],lines=[`${row[0].toFixed(3)} ns`];
  if(p.signals.has('in'))lines.push(`IN   ${row[1].toFixed(3)} V`);
  if(p.signals.has('out'))lines.push(`OUT  ${row[2].toFixed(3)} V`);
  tip.textContent=lines.join('\n');tip.style.left=`${Math.min(px+14,rect.width-130)}px`;tip.style.top=`${Math.max(12,event.clientY-rect.top-72)}px`;tip.hidden=false;
}
async function loadLayout(){
  if(!state.report)return;
  const process=state.process,run=state.run,fields={process,run};
  const [data,rc]=await Promise.all([
    api(query('/api/layout',fields)),
    state.report.checks?.rc_network?api(query('/api/layout-rc',fields)).catch(err=>{notice(`R-C overlay unavailable: ${err.message}`,true);return null;}):Promise.resolve(null)
  ]);
  if(process!==state.process||run!==state.run)return;
  state.layout=data;state.rcLayout=rc;state.rcSelection=null;state.layers=new Set(data.layers.map(layer=>layer.key));state.layoutZoom=1;state.layoutPan=[0,0];
  $('rc-canvas-detail').hidden=true;
  $('layout-count').textContent=`${data.shape_count.toLocaleString()} polygons · ${data.layers.length} layers${rc?` · ${rc.segments.length} R · ${rc.capacitors.length} C`:''}`;
  const list=$('layer-list');clear(list);
  for(const layer of data.layers){const label=add(list,'label',undefined,'layer-row');const input=add(label,'input');input.type='checkbox';input.checked=true;input.dataset.layer=layer.key;const swatch=add(label,'span',undefined,'layer-color');swatch.style.background=layer.color;add(label,'span',layer.name);add(label,'span',layer.count,'count');input.addEventListener('change',()=>{input.checked?state.layers.add(layer.key):state.layers.delete(layer.key);drawLayout();drawComparison();});}
  renderRcPanel();requestAnimationFrame(drawLayout);
  configureComparison();loadComparison();
  loadAnalysis();
}
function layoutTransform(w,h,bbox){const [x0,y0,x1,y1]=bbox,scale=Math.min((w-80)/(x1-x0),(h-80)/(y1-y0))*state.layoutZoom,cx=(x0+x1)/2,cy=(y0+y1)/2;return {x:v=>w/2+(v-cx)*scale+state.layoutPan[0],y:v=>h/2-(v-cy)*scale+state.layoutPan[1],inverseX:px=>(px-w/2-state.layoutPan[0])/scale+cx,inverseY:py=>-(py-h/2-state.layoutPan[1])/scale+cy};}
const rcColors={IN:'#5ad9e9',OUT:'#f6b76a',VDD:'#d4a6ff',VSS:'#98e4a7'};
function drawRcLink(ctx,tr,item,color,width,dashed=false){
  const [ax,ay]=item.a_xy,[bx,by]=item.b_xy,x1=tr.x(ax),y1=tr.y(ay),x2=tr.x(bx),y2=tr.y(by);
  ctx.save();ctx.strokeStyle=color;ctx.fillStyle=color;ctx.lineWidth=width;ctx.setLineDash(dashed?[5,4]:[]);
  ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();ctx.setLineDash([]);
  for(const [x,y] of [[x1,y1],[x2,y2]]){ctx.beginPath();ctx.arc(x,y,width>3?4.5:2.5,0,Math.PI*2);ctx.fill();}
  ctx.restore();
}
function drawLayout(){
  const data=state.layout;if(!data||state.view!=='layout')return;
  const canvas=$('layout-canvas'),{ctx,w,h}=canvasSetup(canvas),tr=layoutTransform(w,h,data.bbox);
  ctx.fillStyle='#081b26';ctx.fillRect(0,0,w,h);ctx.strokeStyle='#173340';ctx.lineWidth=1;
  for(let x=0;x<w;x+=30){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke();}
  for(let y=0;y<h;y+=30){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();}
  for(const layer of data.layers){if(!state.layers.has(layer.key))continue;ctx.fillStyle=layer.color+'99';ctx.strokeStyle=layer.color;ctx.lineWidth=1;for(const poly of layer.polygons){ctx.beginPath();for(const ring of [poly.hull,...poly.holes]){for(let j=0;j<ring.length;j++){const [x,y]=ring[j];if(j===0)ctx.moveTo(tr.x(x),tr.y(y));else ctx.lineTo(tr.x(x),tr.y(y));}ctx.closePath();}ctx.fill('evenodd');ctx.stroke();}}
  const rc=state.rcLayout;
  if(rc){
    if(state.rcShowR)for(const item of rc.segments){if(state.rcNet!=='all'&&item.net!==state.rcNet)continue;drawRcLink(ctx,tr,item,rcColors[item.net]+'b5',2.2,true);}
    if(state.rcShowC)for(const item of rc.capacitors){if(state.rcNet!=='all'&&item.net_a!==state.rcNet&&item.net_b!==state.rcNet)continue;drawRcLink(ctx,tr,item,'#ffe29d88',1.3,true);}
    if(state.rcSelection){const collection=state.rcSelection.kind==='R'?rc.segments:rc.capacitors;const item=collection.find(row=>row.id===state.rcSelection.id);if(item)drawRcLink(ctx,tr,item,'#ffffff',5);}
  }
  canvas._layoutTransform=tr;
}
function configureComparison(){
  const select=$('compare-run');clear(select);
  const runs=state.overview.runs[state.process]||[];
  const selectedIndex=runs.findIndex(item=>item.id===state.run);
  const options=runs.slice(selectedIndex+1).filter(item=>item.status==='passed');
  for(const item of options){const option=add(select,'option',`${item.layout_variant||'legacy'} · ${item.id.slice(0,8)}`);option.value=item.id;}
  const preferred=state.comparisonRun||state.report?.comparison_run_id;
  const chosen=options.find(item=>item.id===preferred)||options.find(item=>item.layout_variant==='standard')||options.find(item=>item.layout_variant==='original')||options[0];
  state.comparisonRun=chosen?.id||null;select.value=state.comparisonRun||'';select.disabled=!chosen;
}
async function loadComparison(){
  const process=state.process,newRun=state.run,oldRun=state.comparisonRun;
  state.comparison=null;$('compare-summary').textContent=oldRun?'Reading and comparing the two hashed GDS snapshots…':'No earlier passed run is available for comparison.';
  for(const id of ['compare-old-canvas','compare-new-canvas']){const {ctx,w,h}=canvasSetup($(id));ctx.fillStyle='#081b26';ctx.fillRect(0,0,w,h);}
  for(const id of ['compare-old-label','compare-new-label','compare-old-foot','compare-new-foot','compare-scope'])$(id).textContent='';
  clear($('compare-layer-summary'));
  $('compare-probe').textContent='Click either layout to inspect the same coordinate in both.';
  if(!oldRun)return;
  try{
    const data=await api(query('/api/layout-comparison',{process,old:oldRun,new:newRun}));
    if(process!==state.process||newRun!==state.run||oldRun!==state.comparisonRun)return;
    state.comparison=data;state.comparisonZoom=1;state.comparisonPan=[0,0];state.comparisonProbe=null;
    renderComparison();requestAnimationFrame(drawComparison);
  }catch(err){if(process===state.process&&newRun===state.run&&oldRun===state.comparisonRun)$('compare-summary').textContent=`Comparison unavailable: ${err.message}`;}
}
function compareTransform(w,h,bbox){
  const [x0,y0,x1,y1]=bbox,cx=(x0+x1)/2,cy=(y0+y1)/2,scale=Math.min((w-42)/(x1-x0),(h-42)/(y1-y0))*state.comparisonZoom;
  return {x:v=>w/2+(v-cx)*scale+state.comparisonPan[0],y:v=>h/2-(v-cy)*scale+state.comparisonPan[1],
    inverseX:px=>(px-w/2-state.comparisonPan[0])/scale+cx,inverseY:py=>-(py-h/2-state.comparisonPan[1])/scale+cy};
}
function comparePolygon(ctx,tr,poly,fill,stroke,width=1){
  ctx.beginPath();for(const ring of [poly.hull,...poly.holes]){ring.forEach(([x,y],i)=>i?ctx.lineTo(tr.x(x),tr.y(y)):ctx.moveTo(tr.x(x),tr.y(y)));ctx.closePath();}
  ctx.fillStyle=fill;ctx.strokeStyle=stroke;ctx.lineWidth=width;ctx.fill('evenodd');ctx.stroke();
}
function drawComparison(){
  const comparison=state.comparison;if(!comparison||state.view!=='layout')return;
  for(const [side,id,highlight] of [['old','compare-old-canvas','#f48b83'],['new','compare-new-canvas','#75efb5']]){
    const canvas=$(id),{ctx,w,h}=canvasSetup(canvas),tr=compareTransform(w,h,comparison.bbox),data=comparison[side];
    ctx.fillStyle='#081b26';ctx.fillRect(0,0,w,h);ctx.strokeStyle='#173340';ctx.lineWidth=1;
    for(let x=0;x<w;x+=30){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,h);ctx.stroke();}
    for(let y=0;y<h;y+=30){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(w,y);ctx.stroke();}
    for(const layer of data.layers){if(!state.layers.has(layer.key))continue;
      for(const poly of layer.polygons)comparePolygon(ctx,tr,poly,layer.color+'77',layer.color+'aa');
      if(state.comparisonHighlight){const indexes=comparison.difference[side==='old'?'old_only':'new_only'][layer.key]||[];
        for(const index of indexes)comparePolygon(ctx,tr,layer.polygons[index],highlight+'88',highlight,2.3);}
    }
    if(state.comparisonProbe){const px=tr.x(state.comparisonProbe[0]),py=tr.y(state.comparisonProbe[1]);
      ctx.save();ctx.strokeStyle='#ffe8a0';ctx.lineWidth=1.5;ctx.setLineDash([4,4]);ctx.beginPath();ctx.moveTo(px,0);ctx.lineTo(px,h);ctx.moveTo(0,py);ctx.lineTo(w,py);ctx.stroke();ctx.setLineDash([]);ctx.beginPath();ctx.arc(px,py,5,0,Math.PI*2);ctx.stroke();ctx.restore();}
    canvas._compareTransform=tr;
  }
}
function pointInRing(point,ring){
  const [x,y]=point;let inside=false;
  for(let i=0,j=ring.length-1;i<ring.length;j=i++){
    const [xi,yi]=ring[i],[xj,yj]=ring[j];
    if((yi>y)!==(yj>y)&&x<(xj-xi)*(y-yi)/(yj-yi)+xi)inside=!inside;
  }
  return inside;
}
function layersAt(data,point){
  const names=[];for(const layer of data.layers){if(!state.layers.has(layer.key))continue;
    if(layer.polygons.some(poly=>pointInRing(point,poly.hull)&&!poly.holes.some(hole=>pointInRing(point,hole))))names.push(layer.name);
  }return names;
}
function probeComparison(point){
  const comparison=state.comparison;if(!comparison)return;state.comparisonProbe=point;
  const oldLayers=layersAt(comparison.old,point),newLayers=layersAt(comparison.new,point);
  $('compare-probe').textContent=`x ${point[0].toFixed(3)} µm · y ${point[1].toFixed(3)} µm — earlier: ${oldLayers.join(', ')||'no visible polygon'}; selected: ${newLayers.join(', ')||'no visible polygon'}. Layer membership at this point is geometry, not connectivity.`;
  drawComparison();
}
function renderComparison(){
  const d=state.comparison;if(!d)return;
  const old=d.old_measurements,newer=d.new_measurements,diff=d.difference;
  const delta=(a,b,unit)=>a==null||b==null?'unavailable':`${(b-a).toFixed(3)} ${unit}`;
  $('compare-summary').textContent=`${diff.removed_polygons} earlier-only and ${diff.added_polygons} selected-only polygons across ${diff.layers.filter(row=>row.old_only||row.new_only).length} layers. R-C delay change: tPHL ${delta(old.rc_tphl_ps,newer.rc_tphl_ps,'ps')}; tPLH ${delta(old.rc_tplh_ps,newer.rc_tplh_ps,'ps')}. Extracted top-level C change: ${delta(old.rc_cap_ff,newer.rc_cap_ff,'fF')}.`;
  $('compare-old-label').textContent=`${$('compare-run').selectedOptions[0]?.textContent||'earlier'} · GDS ${old.gds_sha256.slice(0,10)}`;
  $('compare-new-label').textContent=`${state.report?.layout_variant||'selected'} · ${newer.run_id.slice(0,8)} · GDS ${newer.gds_sha256.slice(0,10)}`;
  $('compare-old-foot').textContent=`${old.shape_count} polygons · R-C ${old.rc_tphl_ps?.toFixed(2)??'—'} / ${old.rc_tplh_ps?.toFixed(2)??'—'} ps · C ${old.rc_cap_ff?.toFixed(3)??'—'} fF`;
  $('compare-new-foot').textContent=`${newer.shape_count} polygons · R-C ${newer.rc_tphl_ps?.toFixed(2)??'—'} / ${newer.rc_tplh_ps?.toFixed(2)??'—'} ps · C ${newer.rc_cap_ff?.toFixed(3)??'—'} fF`;
  $('compare-probe').textContent='Click either layout to inspect the same coordinate in both.';
  $('compare-scope').textContent=d.scope;
  const list=$('compare-layer-summary');clear(list);
  for(const layer of diff.layers.filter(row=>row.old_only||row.new_only)){
    const card=add(list,'div',undefined,'compare-layer-item');add(card,'strong',layer.name);add(card,'span',`${layer.old_only} removed · ${layer.new_only} added`);
  }
  if(!list.children.length)add(list,'div','Every polygon matches at the recorded GDS coordinates.','empty-state');
}
function attachComparisonEvents(){
  $('compare-run').addEventListener('change',event=>{state.comparisonRun=event.target.value;loadComparison();});
  $('compare-highlight').addEventListener('change',event=>{state.comparisonHighlight=event.target.checked;drawComparison();});
  $('compare-fit').addEventListener('click',()=>{state.comparisonZoom=1;state.comparisonPan=[0,0];drawComparison();});
  $('toggle-layers').addEventListener('click',()=>drawComparison());
  window.addEventListener('resize',()=>{if(state.view==='layout')drawComparison();});
  for(const id of ['compare-old-canvas','compare-new-canvas']){
    const canvas=$(id);
    canvas.addEventListener('wheel',event=>{if(!state.comparison)return;event.preventDefault();state.comparisonZoom=Math.max(.35,Math.min(12,state.comparisonZoom*(event.deltaY<0?1.17:.85)));drawComparison();},{passive:false});
    canvas.addEventListener('pointerdown',event=>{if(!state.comparison)return;canvas.setPointerCapture(event.pointerId);canvas._compareStart=[event.clientX,event.clientY,...state.comparisonPan];canvas._compareMoved=false;});
    canvas.addEventListener('pointermove',event=>{if(!canvas._compareStart)return;const dx=event.clientX-canvas._compareStart[0],dy=event.clientY-canvas._compareStart[1];if(Math.hypot(dx,dy)>3)canvas._compareMoved=true;if(canvas._compareMoved){state.comparisonPan=[canvas._compareStart[2]+dx,canvas._compareStart[3]+dy];drawComparison();}});
    canvas.addEventListener('pointerup',event=>{if(!canvas._compareStart)return;const moved=canvas._compareMoved;canvas._compareStart=null;if(!moved&&canvas._compareTransform){const rect=canvas.getBoundingClientRect(),tr=canvas._compareTransform;probeComparison([tr.inverseX(event.clientX-rect.left),tr.inverseY(event.clientY-rect.top)]);}});
    canvas.addEventListener('pointercancel',()=>canvas._compareStart=null);
  }
}
function renderRcPanel(){
  const rc=state.rcLayout;$('rc-show-resistors').disabled=!rc;$('rc-show-capacitors').disabled=!rc;$('rc-net-filter').disabled=!rc;
  $('rc-layout-count').textContent=rc?`${rc.segments.length} resistors · ${rc.capacitors.length} capacitors · ${rc.total_ff.toFixed(3)} fF`:'No R-C network in this run';
  $('rc-layout-note').textContent=rc?rc.geometry_note:'Select a recent validated R-C run to inspect its extracted network on this GDS.';
  const summary=$('rc-net-summary');clear(summary);const terminals=$('rc-terminal-table');clear(terminals);
  if(!rc){clear($('rc-resistor-list'));clear($('rc-capacitor-list'));$('rc-selected-detail').textContent='No R-C overlay for this run.';$('rc-canvas-detail').hidden=true;return;}
  for(const net of rc.nets){const card=add(summary,'div',undefined,'rc-net-card');add(card,'strong',net.name,`rc-net-${net.name}`);add(card,'small',`${net.resistors} segments · largest ${net.largest_ohm.toFixed(2)} Ω`);}
  for(const item of rc.terminals){const card=add(terminals,'div',undefined,'rc-terminal');add(card,'strong',`${item.device} ${item.terminal}`);add(card,'span',`${item.net} → ${item.node}`);add(card,'span',`${item.effective_ohm.toFixed(3)} Ω`);}
  renderRcLists();
}
function renderRcLists(){
  const rc=state.rcLayout;if(!rc)return;
  for(const [kind,id,items] of [['R','rc-resistor-list',rc.segments],['C','rc-capacitor-list',rc.capacitors]]){
    const list=$(id);clear(list);
    const visible=items.filter(item=>state.rcNet==='all'||(kind==='R'?item.net===state.rcNet:item.net_a===state.rcNet||item.net_b===state.rcNet));
    if(!visible.length)add(list,'div','No elements for this net.','empty-state');
    for(const item of visible){const button=add(list,'button',undefined,'rc-element');button.type='button';button.dataset.rcKind=kind;button.dataset.rcId=item.id;add(button,'span',`${item.id} ${item.a} → ${item.b}`);add(button,'span',kind==='R'?`${item.ohm.toFixed(3)} Ω`:`${item.ff.toFixed(5)} fF`);button.classList.toggle('selected',state.rcSelection?.kind===kind&&state.rcSelection?.id===item.id);button.addEventListener('click',()=>selectRcElement(kind,item.id));}
  }
}
function selectRcElement(kind,id){
  const rc=state.rcLayout;if(!rc)return;
  const item=(kind==='R'?rc.segments:rc.capacitors).find(row=>row.id===id);if(!item)return;
  state.rcSelection={kind,id};if(kind==='R'){state.rcShowR=true;$('rc-show-resistors').checked=true;}else{state.rcShowC=true;$('rc-show-capacitors').checked=true;}
  $('rc-selected-detail').textContent=`${id}: ${item.a} (${item.a_xy.map(v=>v.toFixed(3)).join(', ')} µm) → ${item.b} (${item.b_xy.map(v=>v.toFixed(3)).join(', ')} µm) · ${kind==='R'?`${item.ohm.toFixed(4)} Ω`:`${item.ff.toFixed(5)} fF`}. Anchors mark extracted nodes; the straight line is not the routed path.`;
  $('rc-canvas-detail').textContent=`${id} · ${item.a} → ${item.b} · ${kind==='R'?`${item.ohm.toFixed(3)} Ω`:`${item.ff.toFixed(5)} fF`} · node link, not routed path`;$('rc-canvas-detail').hidden=false;
  for(const button of document.querySelectorAll('.rc-element'))button.classList.toggle('selected',button.dataset.rcKind===kind&&button.dataset.rcId===id);
  drawLayout();$('layout-canvas').scrollIntoView({behavior:'smooth',block:'center'});
}
function attachRcEvents(){
  $('rc-show-resistors').addEventListener('change',event=>{state.rcShowR=event.target.checked;if(!state.rcShowR&&state.rcSelection?.kind==='R'){state.rcSelection=null;$('rc-canvas-detail').hidden=true;}drawLayout();});
  $('rc-show-capacitors').addEventListener('change',event=>{state.rcShowC=event.target.checked;if(!state.rcShowC&&state.rcSelection?.kind==='C'){state.rcSelection=null;$('rc-canvas-detail').hidden=true;}drawLayout();});
  $('rc-net-filter').addEventListener('change',event=>{state.rcNet=event.target.value;state.rcSelection=null;$('rc-canvas-detail').hidden=true;$('rc-selected-detail').textContent='Select a resistor or capacitor to highlight its anchors on the GDS.';renderRcLists();drawLayout();});
  const canvas=$('layout-canvas');
  canvas.addEventListener('pointerdown',event=>{canvas._rcStart=[event.clientX,event.clientY];canvas._rcDragged=false;});
  canvas.addEventListener('pointermove',event=>{if(canvas._rcStart&&Math.hypot(event.clientX-canvas._rcStart[0],event.clientY-canvas._rcStart[1])>5)canvas._rcDragged=true;});
  canvas.addEventListener('click',event=>{
    if(canvas._rcDragged||!state.rcLayout||!canvas._layoutTransform)return;
    const rect=canvas.getBoundingClientRect(),px=event.clientX-rect.left,py=event.clientY-rect.top,tr=canvas._layoutTransform;
    let nearest=null,best=12;
    for(const [kind,items,enabled] of [['R',state.rcLayout.segments,state.rcShowR],['C',state.rcLayout.capacitors,state.rcShowC]]){
      if(!enabled)continue;
      for(const item of items){if(state.rcNet!=='all'&&(kind==='R'?item.net!==state.rcNet:item.net_a!==state.rcNet&&item.net_b!==state.rcNet))continue;
        const [ax,ay]=item.a_xy,[bx,by]=item.b_xy,x1=tr.x(ax),y1=tr.y(ay),x2=tr.x(bx),y2=tr.y(by),dx=x2-x1,dy=y2-y1;
        const t=Math.max(0,Math.min(1,((px-x1)*dx+(py-y1)*dy)/(dx*dx+dy*dy||1)));
        const distance=Math.hypot(px-x1-t*dx,py-y1-t*dy);
        if(distance<best){best=distance;nearest={kind,id:item.id};}
      }
    }
    if(nearest)selectRcElement(nearest.kind,nearest.id);
  });
}
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
  $('xschem-image').hidden=true;
  $('editor-status').textContent='Netlisting and rendering Xschem source in the local worker…';
  const data=await api(query('/api/schematic',{process}));
  if(process!==state.process)return;
  if(state.schematic?.source_sha256&&state.schematic.source_sha256!==data.source_sha256){state.editorExperiment=null;$('schematic-sim-status').textContent='Source changed; run a new exploratory simulation.';}
  state.schematic=data;
  $('editor-source').textContent=data.source;
  $('xschem-netlist').textContent=data.netlist;
  $('xschem-image').src=query('/api/schematic.svg',{process,sha:data.preview_sha256});
  $('xschem-image').hidden=false;
  $('editor-status').textContent=`${data.recognized_inverter?'Two-transistor inverter connectivity recognized':'Schematic changed: inspect generated netlist'} · ${data.native_editor_available?'native Xschem ready':'native Xschem GUI unavailable'}`;
  const simulators=$('simulator-status');clear(simulators);
  add(simulators,'div',data.ngspice_executable_found?'ngspice: installed on this Mac; dashboard transients run natively.':'ngspice: unavailable on this Mac; Docker worker fallback may be used.','interpretation-item');
  add(simulators,'div',data.spectre_executable_found?'Spectre executable found; license and compatible model validation are still required.':'Spectre: no executable found on this Mac. Licensed Cadence access and compatible models are required.','interpretation-item');
  $('open-xschem').disabled=!data.native_editor_available;
  $('open-xschem').title=data.native_editor_available?'Open this .sch in native Xschem':'Start XQuartz and refresh the schematic to enable the native editor';
}
function attachSchematicEvents(){
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
    const button=event.currentTarget;button.disabled=true;$('schematic-sim-status').textContent='Running source netlist in local ngspice…';
    try{
      const body={process:state.process,source_sha256:state.schematic.source_sha256};
      const result=await api('/api/simulate-schematic',{method:'POST',headers:{'Content-Type':'application/json','X-Lab-Token':state.overview.token},body:JSON.stringify(body)});
      state.editorExperiment=result;$('schematic-sim-status').textContent=`Exploratory run ${result.manifest.id.slice(0,8)} · source ${result.manifest.schematic_sha256.slice(0,12)} · ${result.samples.length.toLocaleString()} samples`;
      requestAnimationFrame(()=>drawPlot($('schematic-canvas'),result.samples));
      notice('Edited Xschem source simulated; DRC/LVS/PEX evidence remains tied to its selected validation run.');
    }catch(err){$('schematic-sim-status').textContent=`Simulation failed: ${err.message}`;notice(err.message,true);}finally{button.disabled=false;}
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
  const fields={process:state.process,run:state.run,kind:$('pex-kind').value};
  const data=await api(query('/api/pex',fields));
  if(state.run!==fields.run||state.process!==fields.process||$('pex-kind').value!==fields.kind)return;
  state.pex=data;
  const grid=$('pex-metrics');clear(grid);
  for(const [label,value,sub] of [['Top-level C',`${data.top_total_ff.toFixed(3)} fF`,`${data.capacitors.length} inverter-net capacitors`],['All C',String(data.all_capacitor_count),'all extracted capacitors'],['Wire R',String(data.resistors.length),data.kind==='rcx'?'explicit segments in inverter':'excluded from this netlist'],['Delay penalty',`${data.delay_delta_ps.tphl?.toFixed(2)??'—'} ps`,'tPHL vs schematic']]){
    const card=add(grid,'div',undefined,'metric-card');add(card,'div',label,'label');add(card,'div',value,'value');add(card,'div',sub,'sub');
  }
  const table=$('pex-capacitors');clear(table);const head=add(table,'div',undefined,'pex-row head');for(const name of ['Element','Node A','Node B','fF'])add(head,'span',name);
  for(const capacitor of data.capacitors){const row=add(table,'div',undefined,'pex-row');for(const value of [capacitor.name,capacitor.a,capacitor.b,capacitor.ff.toFixed(5)])add(row,'span',value);}
  const rtable=$('pex-resistors');clear(rtable);const rhead=add(rtable,'div',undefined,'pex-row head');for(const name of ['Element','Node A','Node B','Ω'])add(rhead,'span',name);
  if(!data.resistors.length)add(rtable,'div','No distributed wire resistors in this netlist.','empty-state');
  for(const resistor of data.resistors){const row=add(rtable,'div',undefined,'pex-row');for(const value of [resistor.name,resistor.a,resistor.b,resistor.ohm.toFixed(4)])add(row,'span',value);}
  const scope=$('pex-scope');clear(scope);for(const item of [data.scope,'Compare delays using the same model corner, input and load.','This is simulation evidence, not silicon measurement.'])add(scope,'div',item,'interpretation-item');
  const netlist=await api(query('/api/artifact',{...fields,name:data.netlist}));
  if(state.run===fields.run)$('pex-netlist').textContent=netlist.text;
  loadAnalysis();
  loadPexBench().catch(err=>{$('pex-bench-status').textContent=`Testbench unavailable: ${err.message}`;});
}
const benchLabels={supply_v:'Supply',corner:'Model corner',temperature_c:'Temperature',output_load_ff:'Output load',input_pulse:'Input pulse',time_step_ps:'Transient step',stop_ns:'Stop time',measures:'Measurements',input_start_v:'VIN start',input_stop_v:'VIN stop',input_step_v:'VIN step',input_bias_v:'VIN DC bias',ac_amplitude_v:'AC source amplitude',start_hz:'AC start',stop_hz:'AC stop',points_per_decade:'Points per decade',trip_v:'Switching point',vout_at_zero_v:'VOUT at VIN = 0',vout_at_supply_v:'VOUT at VIN = VDD',gain_at_1khz_db:'Gain at 1 kHz',phase_at_1khz_deg:'Phase at 1 kHz',bandwidth_3db_hz:'−3 dB bandwidth',tphl_ps:'tPHL',tplh_ps:'tPLH',fall_90_10_ps:'Output fall 90–10%',rise_10_90_ps:'Output rise 10–90%',input_rise_ns:'Input rise crossing',input_fall_ns:'Input fall crossing'};
function benchFormat(key,value){
  if(value==null)return 'Not reached in sweep';
  if(key.endsWith('_hz'))return `${Number(value).toExponential(3)} Hz`;
  if(key.endsWith('_ps'))return `${Number(value).toFixed(3)} ps`;
  if(key.endsWith('_ns'))return `${Number(value).toFixed(4)} ns`;
  if(key.endsWith('_ff'))return `${value} fF`;
  if(key.endsWith('_db'))return `${value} dB`;
  if(key.endsWith('_deg'))return `${value}°`;
  if(key.endsWith('_v'))return `${value} V`;
  if(key.endsWith('_c'))return `${value} °C`;
  return String(value);
}
function benchRows(parent,items){clear(parent);for(const [key,value] of Object.entries(items)){const row=add(parent,'div',undefined,'parameter-row');add(row,'span',benchLabels[key]||key);add(row,'span',benchFormat(key,value));}}
function drawPexBench(){
  const data=state.pexBench;if(!data||state.view!=='pex')return;
  const canvas=$('pex-bench-canvas');
  if(data.analysis==='transient'){drawPlot(canvas,data.samples);return;}
  const {ctx,w,h}=canvasSetup(canvas),pad={l:60,r:24,t:23,b:39},rows=data.samples;
  const ac=data.analysis==='ac',first=rows[0],last=rows[rows.length-1],x0=ac?Math.log10(first[0]):first[1],x1=ac?Math.log10(last[0]):last[1];
  const ys=rows.map(row=>row[ac?1:2]),y0=ac?Math.floor(Math.min(...ys)-3):0,y1=ac?Math.ceil(Math.max(...ys)+3):data.settings.supply_v;
  const x=value=>pad.l+(value-x0)/(x1-x0)*(w-pad.l-pad.r),y=value=>h-pad.b-(value-y0)/(y1-y0)*(h-pad.t-pad.b);
  ctx.fillStyle='#091c27';ctx.fillRect(0,0,w,h);ctx.strokeStyle='#254553';ctx.fillStyle='#93b7bf';ctx.font='11px ui-monospace,monospace';ctx.lineWidth=1;
  for(let i=0;i<=5;i++){const xx=pad.l+i*(w-pad.l-pad.r)/5;ctx.beginPath();ctx.moveTo(xx,pad.t);ctx.lineTo(xx,h-pad.b);ctx.stroke();ctx.fillText(ac?`10^${Math.round(x0+i*(x1-x0)/5)}`:(x0+i*(x1-x0)/5).toFixed(1),xx-16,h-12);}
  for(let i=0;i<=4;i++){const yy=pad.t+i*(h-pad.t-pad.b)/4;ctx.beginPath();ctx.moveTo(pad.l,yy);ctx.lineTo(w-pad.r,yy);ctx.stroke();ctx.fillText((y1-i*(y1-y0)/4).toFixed(ac?0:1),7,yy+4);}
  ctx.strokeStyle='#f6b76a';ctx.lineWidth=2.5;ctx.beginPath();rows.forEach((row,i)=>{const xx=x(ac?Math.log10(row[0]):row[1]),yy=y(row[ac?1:2]);i?ctx.lineTo(xx,yy):ctx.moveTo(xx,yy);});ctx.stroke();
}
async function loadPexBench(){
  if(!state.report)return;
  const fields={process:state.process,run:state.run,kind:$('pex-kind').value,analysis:$('pex-analysis-kind').value};
  $('pex-bench-status').textContent='Running or reading the selected extracted testbench…';state.pexBench=null;
  const data=await api(query('/api/pex-testbench',fields));
  if(fields.process!==state.process||fields.run!==state.run||fields.kind!==$('pex-kind').value||fields.analysis!==$('pex-analysis-kind').value)return;
  state.pexBench=data;
  $('pex-bench-status').textContent=`${data.evidence} · ${data.engine} · extracted ${data.pex_sha256.slice(0,12)} · deck ${data.deck_sha256.slice(0,12)}`;
  benchRows($('pex-bench-settings'),data.settings);benchRows($('pex-bench-results'),data.results);
  $('pex-bench-deck').textContent=data.deck;
  $('pex-bench-caption').textContent=data.analysis==='ac'?'Frequency in Hz on a log scale · output gain in dB; phase is listed above.':data.analysis==='dc'?'VIN in V · VOUT in V. Switching point is where VOUT = VIN.':'Time in ns · V(IN) cyan and V(OUT) orange.';
  requestAnimationFrame(drawPexBench);
}
function attachEvidenceEvents(){
  $('pex-kind').addEventListener('change',()=>loadPex().catch(err=>notice(err.message,true)));
  $('pex-analysis-kind').addEventListener('change',()=>loadPexBench().catch(err=>{$('pex-bench-status').textContent=`Testbench unavailable: ${err.message}`;}));
  window.addEventListener('resize',()=>{if(state.view==='pex'&&state.pexBench)drawPexBench();});
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
function attachWorkbenchEvents(){
  $('pipeline').addEventListener('click',event=>{const button=event.target.closest('[data-checkpoint]');if(button)openCheckpoint(button.dataset.checkpoint);});
  $('checkpoint-close').addEventListener('click',()=>$('checkpoint-dialog').close());
  $('checkpoint-dialog').addEventListener('click',event=>{if(event.target===$('checkpoint-dialog'))event.target.close();});
  $('checkpoint-open-view').addEventListener('click',event=>{
    const button=event.currentTarget,kind=button.dataset.waveKind;
    if(kind){state.waveKind=kind;for(const el of document.querySelectorAll('[data-wave]'))el.classList.toggle('selected',el.dataset.wave===kind);}
    $('checkpoint-dialog').close();setView(button.dataset.view);
  });
  $('testbench-select').addEventListener('change',()=>loadTestbench().catch(err=>notice(err.message,true)));
  for(const input of document.querySelectorAll('[data-signal]'))input.addEventListener('change',()=>{
    input.checked?state.waveSignals.add(input.dataset.signal):state.waveSignals.delete(input.dataset.signal);
    $('wave-tooltip').hidden=true;
    if(state.wave)drawPlot($('wave-canvas'),state.wave.samples,state.waveSignals);
  });
}
async function simulate(event){event.preventDefault();const button=event.currentTarget.querySelector('button[type=submit]');button.disabled=true;$('experiment-status').textContent='Running local ngspice…';try{const body={process:state.process,voltage:Number($('exp-voltage').value),load_ff:Number($('exp-load').value),temp_c:Number($('exp-temp').value)};const data=await api('/api/simulate',{method:'POST',headers:{'Content-Type':'application/json','X-Lab-Token':state.overview.token},body:JSON.stringify(body)});state.experiment=data;const m=data.manifest;$('experiment-status').textContent='Exploratory run saved';$('experiment-id').textContent=`Experiment ${m.id}`;const box=$('experiment-result');clear(box);for(const [label,value] of [['Process',state.overview.processes[m.process].title],['Supply',`${m.voltage} V`],['Load',`${m.load_ff} fF`],['Temperature',`${m.temp_c} °C`],['VOUT at 0.5 ns',`${m.high_v.toFixed(4)} V`],['VOUT at 2.0 ns',`${m.low_v.toFixed(4)} V`]]){const row=add(box,'div',undefined,'result-line');add(row,'span',label);add(row,'strong',value);}requestAnimationFrame(()=>drawPlot($('experiment-canvas'),data.samples));notice(`Exploratory run ${m.id.slice(0,8)} saved locally.`);}catch(err){$('experiment-status').textContent='Simulation failed';notice(err.message,true);}finally{button.disabled=false;}}
async function rerun(){const button=$('rerun-button');button.disabled=true;try{const layout_variant=state.report?.layout_variant==='fast'?'fast':'standard';const data=await api('/api/validate',{method:'POST',headers:{'Content-Type':'application/json','X-Lab-Token':state.overview.token},body:JSON.stringify({process:state.process,layout_variant})});notice(`${layout_variant} layout validation started. Checking the new report…`);while(true){await new Promise(resolve=>setTimeout(resolve,2000));const job=await api(query('/api/job',{id:data.job_id}));if(job.state==='running')continue;if(job.state==='complete'){state.overview=await api('/api/overview');selectRun();await loadRun();notice(`Mac validation finished: ${job.report_status||'inspect report'} · ${job.run_id?.slice(0,8)||'no report'}`);}else notice(`Validation failed: ${job.output||'inspect worker logs'}`,true);break;}}catch(err){notice(err.message,true);}finally{button.disabled=false;}}
function attachEvents(){$('process-select').addEventListener('change',async event=>{state.process=event.target.value;state.experiment=null;$('experiment-result').innerHTML='<div class="empty-state">Adjust a parameter and simulate to see a new trace.</div>';$('experiment-status').textContent='Ready to simulate';$('exp-voltage').value=state.overview.processes[state.process].voltage;selectRun();await loadRun();});$('run-select').addEventListener('change',async event=>{state.run=event.target.value;await loadRun();});for(const button of document.querySelectorAll('[data-view]'))button.addEventListener('click',()=>setView(button.dataset.view));for(const button of document.querySelectorAll('[data-goto]'))button.addEventListener('click',()=>setView(button.dataset.goto));for(const button of document.querySelectorAll('[data-wave]'))button.addEventListener('click',()=>{state.waveKind=button.dataset.wave;for(const el of document.querySelectorAll('[data-wave]'))el.classList.toggle('selected',el===button);loadWave().catch(err=>notice(err.message,true));});$('copy-netlist').addEventListener('click',()=>navigator.clipboard.writeText($('schematic-code').textContent).then(()=>notice('Netlist copied.')).catch(err=>notice(err.message,true)));$('open-artifact').addEventListener('click',async()=>{try{const data=await api(query('/api/artifact',{process:state.process,run:state.run,name:$('artifact-select').value}));$('artifact-content').textContent=data.text;}catch(err){notice(err.message,true);}});$('experiment-form').addEventListener('submit',simulate);$('rerun-button').addEventListener('click',rerun);$('fit-layout').addEventListener('click',()=>{state.layoutZoom=1;state.layoutPan=[0,0];drawLayout();});$('toggle-layers').addEventListener('click',()=>{const all=state.layers.size!==state.layout.layers.length;state.layers=new Set(all?state.layout.layers.map(layer=>layer.key):[]);for(const input of document.querySelectorAll('[data-layer]'))input.checked=all;drawLayout();});const canvas=$('layout-canvas');canvas.addEventListener('wheel',event=>{event.preventDefault();state.layoutZoom=Math.max(.35,Math.min(12,state.layoutZoom*(event.deltaY<0?1.17:.85)));drawLayout();},{passive:false});canvas.addEventListener('pointerdown',event=>{state.drag=[event.clientX,event.clientY,...state.layoutPan];canvas.setPointerCapture(event.pointerId);});canvas.addEventListener('pointermove',event=>{const rect=canvas.getBoundingClientRect(),tr=canvas._layoutTransform;if(tr)$('layout-coordinates').textContent=`x ${tr.inverseX(event.clientX-rect.left).toFixed(3)} µm · y ${tr.inverseY(event.clientY-rect.top).toFixed(3)} µm`;if(state.drag){state.layoutPan=[state.drag[2]+event.clientX-state.drag[0],state.drag[3]+event.clientY-state.drag[1]];drawLayout();}});canvas.addEventListener('pointerup',()=>state.drag=null);$('wave-canvas').addEventListener('mousemove',plotHover);$('wave-canvas').addEventListener('mouseleave',()=>$('wave-tooltip').hidden=true);window.addEventListener('resize',()=>{if(state.view==='layout')drawLayout();if(state.view==='waveforms'&&state.wave)drawPlot($('wave-canvas'),state.wave.samples,state.waveSignals);if(state.view==='experiments'&&state.experiment)drawPlot($('experiment-canvas'),state.experiment.samples);});}
function attachRcoEvents(){
  $('circuit-select').addEventListener('change',event=>setView(event.target.value==='rco'?'rco':'overview'));
  $('process-select').addEventListener('change',()=>{state.rcoRun=null;if(state.view==='rco')loadRco().catch(err=>notice(err.message,true));});
  $('rco-run-select').addEventListener('change',event=>loadRco(event.target.value).catch(err=>notice(err.message,true)));
  $('rco-run-button').addEventListener('click',simulateRco);
  $('rco-xschem').addEventListener('change',event=>{if(event.target.checked){$('rco-passives').value='pdk';if($('rco-bank-style').value==='guarded'||(state.process==='sky130'&&$('rco-bank-style').value==='balanced'))$('rco-bank-style').value='binary';}});
  $('rco-passives').addEventListener('change',event=>{if(event.target.value==='ideal')$('rco-xschem').checked=false;});
  $('rco-bank-style').addEventListener('change',event=>{if(event.target.value==='guarded'||(state.process==='sky130'&&event.target.value==='balanced'))$('rco-xschem').checked=false;});
  $('rco-open-xschem').addEventListener('click',async()=>{try{const bank_style=$('rco-bank-style').value==='balanced'&&state.process==='gf180'?'balanced':'binary';const result=await api('/api/open-xschem',{method:'POST',headers:{'Content-Type':'application/json','X-Lab-Token':state.overview.token},body:JSON.stringify({process:state.process,circuit:'rco',bank_style})});notice(`Opened ${result.source} in native Xschem.`);}catch(err){notice(err.message,true);}});
  $('rco-open-passive-probe').addEventListener('click',async()=>{try{const result=await api('/api/open-rco-passive-probe',{method:'POST',headers:{'Content-Type':'application/json','X-Lab-Token':state.overview.token},body:JSON.stringify({process:state.process})});notice(`Opened isolated passive test cell in KLayout: ${result.layout}`);}catch(err){notice(err.message,true);}});
  for(const input of document.querySelectorAll('[data-rco-signal]'))input.addEventListener('change',()=>{const bit=Number(input.dataset.rcoSignal);input.checked?state.rcoSignals.add(bit):state.rcoSignals.delete(bit);drawRcoPlot();});
  for(const id of ['rco-canvas','rco-current-canvas']){const canvas=$(id);canvas.addEventListener('pointermove',event=>{const index=rcoSampleAt(event);if(index!=null)inspectRcoWave(index);});canvas.addEventListener('click',event=>{const index=rcoSampleAt(event);if(index!=null)rcoSelectInterval(index);});}
  $('rco-probe-clear').addEventListener('click',()=>{state.rcoIntervalStart=null;state.rcoIntervalEnd=null;$('rco-wave-interval').textContent='Select two times to measure an interval.';drawRcoPlot();drawRcoCurrent();});
  $('rco-range-signal').addEventListener('change',event=>{if(event.target.value==='5'){$('rco-range-min').value=rcoHighCurrentBand()||'';$('rco-range-max').value='';}else if(state.rco?.selected){$('rco-range-min').value=(state.rco.selected.supply_v*.45).toFixed(3);$('rco-range-max').value=(state.rco.selected.supply_v*.55).toFixed(3);}});
  $('rco-range-form').addEventListener('submit',event=>{event.preventDefault();analyzeRcoRange();});
  $('rco-trim-canvas').addEventListener('pointermove',event=>{const points=state.rco?.full_trim?.points;if(!points)return;const code=rcoTrimCodeAt(event);$('rco-full-trim-status').textContent=`Code ${code}: ${(points[code][1]/1000).toFixed(3)} kHz · click to load` ;});
  $('rco-trim-canvas').addEventListener('pointerleave',drawRcoTrim);
  $('rco-trim-canvas').addEventListener('click',event=>{if(!state.rco?.full_trim)return;$('rco-code').value=rcoTrimCodeAt(event);drawRcoCapPlot();});
  $('rco-cap-range').addEventListener('change',drawRcoCapPlot);
  $('rco-code').addEventListener('change',drawRcoCapPlot);
  $('rco-cap-canvas').addEventListener('pointermove',event=>{const rows=state.rco?.bank_ac?.points;if(!rows)return;const code=rcoCapCodeAt(event.clientX,event.currentTarget),delta=code<511?rows[code+1][1]-rows[code][1]:null;$('rco-cap-hover').textContent=`Code ${code}: ${rows[code][1].toFixed(3)} fF${delta!=null?` · next Δ ${delta>=0?'+':''}${delta.toFixed(3)} fF${delta<0?' reversal':''}`:''}`;});
  $('rco-cap-canvas').addEventListener('click',event=>{const rows=state.rco?.bank_ac?.points;if(!rows)return;const code=rcoCapCodeAt(event.clientX,event.currentTarget);$('rco-code').value=code;drawRcoCapPlot();});
  for(const process of ['sky130','gf180']){const [canvasId,regionId]=rcoPlacementIds(process);$(regionId).addEventListener('change',()=>drawRcoPlacement(process));$(canvasId).addEventListener('click',event=>inspectRcoPlacement(process,event));}
  for(const button of document.querySelectorAll('[data-rco-open-placement]'))button.addEventListener('click',async()=>{try{const process=button.dataset.rcoOpenPlacement,result=await api('/api/open-rco-placement',{method:'POST',headers:{'Content-Type':'application/json','X-Lab-Token':state.overview.token},body:JSON.stringify({process})});notice(`Opened ${process} RCO placement GDS and DRC markers in native KLayout.${result.pcell_library?' The GF PCell library is loaded for new instances; the shown GDS cells remain static.':''}`);}catch(err){notice(err.message,true);}});
  window.addEventListener('resize',()=>{if(state.view==='rco'){drawRcoPlot();drawRcoCurrent();drawRcoTrim();drawRcoCapPlot();drawRcoPlacement('sky130');drawRcoPlacement('gf180');}});
}
async function init(){try{state.overview=await api('/api/overview');const select=$('process-select');for(const [id,spec] of Object.entries(state.overview.processes)){const opt=add(select,'option',spec.title);opt.value=id;}select.value=state.process;$('exp-voltage').value=state.overview.processes[state.process].voltage;selectRun();renderDocList();attachEvents();attachEvidenceEvents();attachWorkbenchEvents();attachSchematicEvents();attachRcEvents();attachComparisonEvents();attachRcoEvents();await loadRun();}catch(err){notice(`Dashboard failed to load: ${err.message}`,true);}}
init();
