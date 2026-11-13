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
