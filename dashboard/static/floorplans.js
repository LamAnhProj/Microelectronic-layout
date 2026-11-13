const revisions = [
  {id:'01-original-mirrored.svg',title:'1 · Original mirrored fan + exact centroid',commit:'b3ef34c',note:'Five-row first pass. The central dummy channel and separated bit islands made routing inefficient.'},
  {id:'02-compact-no-center-dummies.svg',title:'2 · Compact, center dummies removed',commit:'e2b9b7e',note:'Removed the interior dummy channel. Some MIM rows were staggered, which made the grid inconsistent.'},
  {id:'03-uniform-grid.svg',title:'3 · Uniform MIM grid',commit:'48c0309',note:'No staggered rows. Several same-bit groups were still split into disconnected islands.'},
  {id:'04-grouped-current.svg',title:'4 · Connected bit groups (current)',commit:'e5ae811',note:'Bit 8 moved to the outer fan edge. Each bit is adjacent within its group; the centered comparison is not an exact common centroid.'},
  {id:'05-exact-centroid-reference.svg',title:'5 · Exact centroid reference',commit:'e5ae811',note:'Preserved separately for teaching and comparison. Some bits must split across the array to obtain exact centroid symmetry.'}
];
const byId = Object.fromEntries(revisions.map(item=>[item.id,item]));
const url = item => `/floorplans/${item.id}`;
function renderPanel(side,id){
  const item=byId[id],panel=document.getElementById(`${side}-panel`);
  panel.querySelector('h2').textContent=item.title;
  panel.querySelector('.revision-meta').textContent=`Git ${item.commit} · SKY130A + GF180MCU D`;
  panel.querySelector('.revision-note').textContent=item.note;
  panel.querySelector('a').href=url(item);
  const img=panel.querySelector('img');img.src=url(item);img.alt=`${item.title}, showing SKY130A and GF180MCU D`;
  panel.querySelector('.edit-revision').onclick=()=>selectEditorRevision(id);
}
function render(){
  renderPanel('left',document.getElementById('left-version').value);
  renderPanel('right',document.getElementById('right-version').value);
  document.getElementById('comparison').classList.toggle('stack',document.getElementById('arrangement').value==='stack');
  const scale=Number(document.getElementById('scale').value);
  document.getElementById('scale-value').textContent=`${scale}%`;
  document.querySelectorAll('.art img').forEach(img=>{img.style.width=`${scale}%`;});
}
for(const side of ['left','right']){
  const select=document.getElementById(`${side}-version`);
  for(const item of revisions){const option=document.createElement('option');option.value=item.id;option.textContent=item.title;select.append(option);}
  select.value=side==='left'?revisions[0].id:revisions[3].id;
  select.addEventListener('change',render);
}
for(const id of ['scale','arrangement'])document.getElementById(id).addEventListener('input',render);
const list=document.getElementById('history-list');list.className='history-grid';
for(const item of revisions){
  const card=document.createElement('article');card.className='history-card';
  const img=document.createElement('img');img.src=url(item);img.alt=item.title;img.loading='lazy';card.append(img);
  const body=document.createElement('div'),title=document.createElement('h3');title.textContent=item.title;body.append(title);
  const meta=document.createElement('p');meta.textContent=`Git ${item.commit} · ${item.note}`;body.append(meta);
  const button=document.createElement('button');button.textContent='Compare on left';button.addEventListener('click',()=>{document.getElementById('left-version').value=item.id;render();document.getElementById('comparison').scrollIntoView({behavior:'smooth'});});body.append(button);
  const link=document.createElement('a');link.href=url(item);link.target='_blank';link.rel='noopener';link.textContent='Full size ↗';body.append(link);card.append(body);list.append(card);
}
render();

// The editor uses site positions exported from the exact saved SVGs. A draft
// contains only the occupant of each site; it never changes the source maps.
const bitColors=['#16a6a4','#57a5db','#8b75d6','#cc6ec3','#e67b9b','#f3956b','#ddb64d','#a6ba46','#477e47'];
const editor={data:null,panel:null,bits:[],selected:null,undo:[],drag:null};
const get=id=>document.getElementById(id);
const draftKey=(revision,panel)=>`chip-lab-floorplan-v1:${revision}:${panel}`;
function countRemaining(bit){
  return editor.panel.counts[bit]-editor.bits.filter(value=>value===bit).length;
}
function status(message){get('editor-status').textContent=message;}
function saveDraft(){
  try{localStorage.setItem(draftKey(get('editor-revision').value,editor.panel.id),JSON.stringify(editor.bits));}
  catch{status('The draft changed, but this browser could not save it locally.');}
}
function validDraft(bits,panel){
  if(!Array.isArray(bits)||bits.length!==panel.tiles.length)return false;
  if(bits.some((bit,i)=>!['D',...Object.keys(panel.counts)].includes(bit)||panel.tiles[i].locked&&bit!=='D'))return false;
  return Object.keys(panel.counts).every(bit=>bits.filter(value=>value===bit).length<=panel.counts[bit]);
}
function renderEditor(){
  const panel=editor.panel;if(!panel)return;
  const board=get('placement-board');board.replaceChildren();board.style.width=`${panel.width+2}px`;board.style.height=`${panel.height+2}px`;
  get('board-title').textContent=panel.title;
  get('board-size').textContent=`${panel.total} trim MIM units · ${panel.tiles.length} sites`;
  panel.tiles.forEach((tile,index)=>{
    const bit=editor.bits[index],button=document.createElement('button');button.type='button';button.className='site';button.textContent=bit;
    button.dataset.bit=bit;button.style.left=`${tile.x}px`;button.style.top=`${tile.y}px`;button.style.width='34px';button.style.height='28px';
    button.style.setProperty('--bit-color',bit==='D'?'#394357':bitColors[Number(bit)]);
    button.disabled=tile.locked;button.draggable=!tile.locked&&bit!=='D';
    button.title=tile.locked?'Fixed dummy perimeter':`Site ${index+1}: ${bit==='D'?'dummy placeholder':`bit ${bit} MIM unit`}`;
    button.setAttribute('aria-label',button.title);
    if(editor.selected?.type==='board'&&editor.selected.index===index)button.classList.add('selected');
    button.addEventListener('click',()=>siteClicked(index));
    button.addEventListener('dragstart',event=>{editor.drag={type:'board',index};event.dataTransfer.setData('text/plain',`site-${index}`);event.dataTransfer.effectAllowed='move';});
    button.addEventListener('dragover',event=>{if(!tile.locked&&editor.drag)event.preventDefault();});
    button.addEventListener('drop',event=>{event.preventDefault();if(editor.drag)moveToSite(index,editor.drag);editor.drag=null;});
    button.addEventListener('dragend',()=>{editor.drag=null;});
    board.append(button);
  });
  const palette=get('palette');palette.replaceChildren();const counts=get('bit-counts');counts.replaceChildren();
  for(let bit=0;bit<9;bit++){
    const name=String(bit),left=countRemaining(name),total=panel.counts[name];
    const chip=document.createElement('span');chip.className='bit-count';chip.style.setProperty('--bit-color',bitColors[bit]);
    chip.innerHTML=`<i></i>bit ${bit}: ${left}/${total} left`;counts.append(chip);
    const button=document.createElement('button');button.type='button';button.style.setProperty('--bit-color',bitColors[bit]);
    button.innerHTML=`${bit}<span>${left} left</span>`;button.disabled=left===0;button.draggable=left>0;
    button.setAttribute('aria-label',`Select bit ${bit}, ${left} of ${total} units left`);
    if(editor.selected?.type==='palette'&&editor.selected.bit===name)button.classList.add('selected');
    button.addEventListener('click',()=>{editor.selected={type:'palette',bit:name};renderEditor();status(`Bit ${bit} selected. Choose an interior site.`);});
    button.addEventListener('dragstart',event=>{editor.drag={type:'palette',bit:name};event.dataTransfer.setData('text/plain',`bit-${bit}`);event.dataTransfer.effectAllowed='copy';});
    button.addEventListener('dragend',()=>{editor.drag=null;});palette.append(button);
  }
  const remaining=Object.keys(panel.counts).reduce((sum,bit)=>sum+countRemaining(bit),0),placed=panel.total-remaining;
  get('remaining-count').textContent=String(remaining);
  get('placed-count').textContent=`${placed} of ${panel.total} placed`;
  get('placement-progress').style.width=`${100*placed/panel.total}%`;
  get('unplace-selected').disabled=editor.selected?.type!=='board';
  get('editor-undo').disabled=editor.undo.length===0;
}
function changeBits(next,message){
  editor.undo.push(editor.bits.slice());if(editor.undo.length>30)editor.undo.shift();
  editor.bits=next;editor.selected=null;saveDraft();renderEditor();status(message);
}
function moveToSite(index,source){
  if(editor.panel.tiles[index].locked)return;
  const next=editor.bits.slice();
  if(source.type==='palette'){
    if(countRemaining(source.bit)<=0)return;
    next[index]=source.bit;
  }else if(source.type==='board'){
    if(source.index===index||editor.panel.tiles[source.index].locked||next[source.index]==='D')return;
    [next[index],next[source.index]]=[next[source.index],next[index]];
  }else return;
  changeBits(next,`Placed bit ${next[index]} at site ${index+1}. ${source.type==='board'?'The two sites exchanged occupants.':'Any displaced unit returned to the tray.'}`);
}
function siteClicked(index){
  if(editor.panel.tiles[index].locked)return;
  if(editor.selected){
    if(editor.selected.type==='board'&&editor.selected.index===index){editor.selected=null;renderEditor();return;}
    moveToSite(index,editor.selected);return;
  }
  if(editor.bits[index]!=='D'){
    editor.selected={type:'board',index};renderEditor();status(`Bit ${editor.bits[index]} selected. Choose another site or return it to the tray.`);
  }else status('This is a dummy placeholder. Select a numbered unit or a bit from the tray first.');
}
function loadEditorPanel(){
  const revision=editor.data.revisions.find(item=>item.id===get('editor-revision').value);
  editor.panel=revision.panels.find(panel=>panel.id===get('editor-panel').value);
  const original=editor.panel.tiles.map(tile=>tile.bit);
  let saved=null;try{saved=JSON.parse(localStorage.getItem(draftKey(revision.id,editor.panel.id)));}catch{}
  editor.bits=validDraft(saved,editor.panel)?saved:original;
  editor.selected=null;editor.undo=[];renderEditor();status(saved&&validDraft(saved,editor.panel)?'Your browser-local draft is loaded.':'Saved floorplan loaded. Start empty to practice placing all units.');
}
function selectEditorRevision(id,scroll=true){
  if(!editor.data)return;
  get('editor-revision').value=id;
  const revision=editor.data.revisions.find(item=>item.id===id),select=get('editor-panel');select.replaceChildren();
  for(const panel of revision.panels){const option=document.createElement('option');option.value=panel.id;option.textContent=panel.title;select.append(option);}
  loadEditorPanel();if(scroll)get('placement-editor').scrollIntoView({behavior:'smooth'});
}
get('editor-panel').addEventListener('change',loadEditorPanel);
get('editor-revision').addEventListener('change',event=>selectEditorRevision(event.target.value));
get('editor-empty').addEventListener('click',()=>changeBits(editor.bits.map(()=>'D'),'Empty practice board ready. Choose a bit from the tray; the remaining count will decrease as you place units.'));
get('editor-reset').addEventListener('click',()=>changeBits(editor.panel.tiles.map(tile=>tile.bit),'Restored this panel to its saved floorplan.'));
get('editor-undo').addEventListener('click',()=>{if(!editor.undo.length)return;editor.bits=editor.undo.pop();editor.selected=null;saveDraft();renderEditor();status('Undid the last placement change.');});
get('editor-export').addEventListener('click',()=>{
  if(!editor.panel)return;
  const revision=get('editor-revision').value,panel=editor.panel;
  const draft={schema_version:1,source_svg:revision,panel:panel.id,process:panel.process,
    site_units:'SVG pixels relative to panel origin; logical placement only',
    total_trim_units:panel.total,remaining_trim_units:Object.keys(panel.counts).reduce((sum,bit)=>sum+countRemaining(bit),0),
    sites:panel.tiles.map((tile,index)=>({...tile,bit:editor.bits[index]}))};
  const blob=new Blob([JSON.stringify(draft,null,2)+'\n'],{type:'application/json'}),link=document.createElement('a');
  link.href=URL.createObjectURL(blob);link.download=`rco-bank-${revision.slice(0,2)}-${panel.id}-draft.json`;
  link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);
  status(`Downloaded ${link.download}. It records logical sites; physical layout validation remains open.`);
});
get('unplace-selected').addEventListener('click',()=>{if(editor.selected?.type!=='board')return;const next=editor.bits.slice(),bit=next[editor.selected.index];next[editor.selected.index]='D';changeBits(next,`Returned one bit ${bit} unit to the tray.`);});
const tray=get('device-tray');tray.addEventListener('dragover',event=>{if(editor.drag?.type==='board'){event.preventDefault();tray.classList.add('drag-over');}});
tray.addEventListener('dragleave',()=>tray.classList.remove('drag-over'));
tray.addEventListener('drop',event=>{event.preventDefault();tray.classList.remove('drag-over');if(editor.drag?.type!=='board')return;const next=editor.bits.slice(),bit=next[editor.drag.index];next[editor.drag.index]='D';editor.drag=null;changeBits(next,`Returned one bit ${bit} unit to the tray.`);});
fetch('/floorplan-data.json').then(response=>{if(!response.ok)throw Error(`HTTP ${response.status}`);return response.json();}).then(data=>{
  editor.data=data;const select=get('editor-revision');
  for(const item of revisions){const option=document.createElement('option');option.value=item.id;option.textContent=item.title;select.append(option);}
  selectEditorRevision(revisions[3].id,false);
}).catch(error=>status(`Could not load editable floorplan sites: ${error.message}`));

const maskColors={m4:'#5583b8',mim:'#62dfc5',m5:'#f2bd61'};
function drawRouted(card,data,visible){
  const canvas=card.querySelector('canvas'),ctx=canvas.getContext('2d');
  const width=Math.max(320,canvas.clientWidth),height=300,ratio=window.devicePixelRatio||1;
  canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);ctx.scale(ratio,ratio);
  ctx.clearRect(0,0,width,height);
  const [xmin,ymin,xmax,ymax]=data.geometry.bbox_um,pad=26;
  const scale=Math.min((width-2*pad)/(xmax-xmin),(height-2*pad)/(ymax-ymin));
  const left=(width-(xmax-xmin)*scale)/2,bottom=(height-(ymax-ymin)*scale)/2;
  const x=value=>left+(value-xmin)*scale,y=value=>height-bottom-(value-ymin)*scale;
  for(const name of ['m4','mim','m5']){
    if(!visible.has(name))continue;
    ctx.fillStyle=maskColors[name];ctx.globalAlpha=name==='m4'?.42:.72;
    for(const polygon of data.geometry.layers[name]){
      if(!polygon.length)continue;
      ctx.beginPath();ctx.moveTo(x(polygon[0][0]),y(polygon[0][1]));
      for(const point of polygon.slice(1))ctx.lineTo(x(point[0]),y(point[1]));
      ctx.closePath();ctx.fill();
    }
  }
  ctx.globalAlpha=1;ctx.font='12px system-ui';ctx.fillStyle='#f5f8ff';
  for(let index=0;index<4;index++)ctx.fillText(`C${index}`,x(42),y(50+14*index)+4);
  ctx.fillText('IN',x(40),y(50)-7);ctx.fillText('GND',x(56),y(92)-7);
}
function renderRouted(process,data){
  const card=get(`routed-${process}`),checks=data.checks;
  card.querySelector('.routed-status').textContent=`Mac run · Magic DRC ${checks.magic_drc_errors} · KLayout DRC ${checks.klayout_drc_items} · LVS unique match · RCX ${checks.rcx.extracted_resistors} resistor${checks.rcx.extracted_resistors===1?'':'s'}`;
  const toggles=card.querySelector('.layer-toggles'),visible=new Set(['m4','mim','m5']);
  for(const [name,label] of [['m4','M4 bottom'],['mim','MIM top'],['m5','M5 route']]){
    const wrapper=document.createElement('label'),checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.checked=true;
    checkbox.addEventListener('change',()=>{checkbox.checked?visible.add(name):visible.delete(name);drawRouted(card,data,visible);});
    const swatch=document.createElement('i');swatch.style.setProperty('--layer-color',maskColors[name]);
    wrapper.append(checkbox,swatch,document.createTextNode(label));toggles.append(wrapper);
  }
  const metrics=card.querySelector('.routed-metrics'),table=document.createElement('table');
  table.innerHTML='<thead><tr><th>Testbench</th><th>AC C at 512 kHz</th><th>Half-supply delay</th></tr></thead><tbody></tbody>';
  for(const [key,label] of [['schematic','Schematic'],['capacitance_pex','Cap PEX'],['distributed_rcx','R-C extraction']]){
    const result=data.results[key],row=document.createElement('tr');
    for(const text of [label,`${(result.ac.capacitance_f*1e15).toFixed(3)} fF`,`${(result.transient.delay_s*1e9).toFixed(3)} ns`]){
      const cell=document.createElement('td');cell.textContent=text;row.append(cell);
    }
    table.tBodies[0].append(row);
  }
  metrics.append(table);
  card.querySelector('.routed-path').textContent=`Saved run ${data.run_id} · ${data.gds}`;
  card.querySelector('.open-routed').addEventListener('click',async()=>{
    try{
      const overview=await fetch('/api/overview').then(response=>response.json());
      const response=await fetch('/api/open-rco-four-mim',{method:'POST',headers:{'Content-Type':'application/json','X-Lab-Token':overview.token},body:JSON.stringify({process})});
      const opened=await response.json();if(!response.ok)throw Error(opened.error||`HTTP ${response.status}`);
      card.querySelector('.routed-path').textContent=`Opened in native KLayout: ${opened.layout} · DRC markers: ${opened.markers}`;
    }catch(error){card.querySelector('.routed-path').textContent=`Could not open KLayout: ${error.message}`;}
  });
  drawRouted(card,data,visible);
  window.addEventListener('resize',()=>drawRouted(card,data,visible));
}
for(const process of ['sky130','gf180']){
  fetch(`/api/rco-four-mim?process=${process}`).then(async response=>{
    const result=await response.json();if(!response.ok)throw Error(result.error||`HTTP ${response.status}`);return result;
  }).then(result=>renderRouted(process,result)).catch(error=>{get(`routed-${process}`).querySelector('.routed-status').textContent=`Evidence unavailable: ${error.message}`;});
}
