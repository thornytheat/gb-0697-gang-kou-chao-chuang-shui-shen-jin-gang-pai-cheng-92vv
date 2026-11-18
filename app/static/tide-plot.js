const chart=JSON.parse(document.getElementById('chart-data').textContent);
const STATION_COLOR={OFFSHORE:'#43b9c6',HARBOR:'#c5a76c',OUTER_ANCHOR:'#89a5ce'};
const graph=document.getElementById('tide-graph');
const tides=chart.tides.slice().sort((a,b)=>Number(a.a)-Number(b.a));
const extent=tides.length?[Number(tides[0].a),Number(tides[tides.length-1].a)]:[0,1];
const max=Math.max(1,...tides.map(r=>Number(r.depth)));
const from=new Date(extent[0]*1000).toISOString(),to=new Date(extent[1]*1000).toISOString();
const crossDay=from.slice(0,10)!==to.slice(0,10);
document.getElementById('time-scale').textContent=tides.length?((crossDay?from.slice(0,16).replace('T',' ')+'—'+to.slice(0,16).replace('T',' '):from.slice(0,10)+' '+from.slice(11,16)+'—'+to.slice(11,16))+' UTC'):'无潮位';

// 分站点堆叠：每站一行柱，颜色区分，缺口处留白。
const byStation={};
for(const r of tides){(byStation[r.station]=byStation[r.station]||[]).push(r)}
for(const station of Object.keys(STATION_COLOR)){
  const row=document.createElement('div');row.className='station-row';
  const label=document.createElement('span');label.className='station-label';label.textContent=station;row.append(label);
  const track=document.createElement('div');track.className='station-track';
  const pts=(byStation[station]||[]).slice().sort((a,b)=>Number(a.a)-Number(b.a));
  const range=extent[1]-extent[0]||1;
  for(const r of pts){
    const bar=document.createElement('i');
    bar.style.left=(Number(r.a)-extent[0])/range*100+'%';
    bar.style.height=Math.max(3,Number(r.depth)/max*100)+'%';
    bar.style.background=STATION_COLOR[station];
    bar.title=station+' · 行'+r.line+' · '+r.start+' · '+r.depth+'m（原始读数 '+r.value+r.unit+'，v'+r.version+'）';
    track.append(bar);
  }
  row.append(track);graph.append(row);
}

// 排程甘特条：确认=青，临时=琥珀，无窗隐藏。
document.querySelectorAll('.track i').forEach(bar=>{
  const a=Number(bar.dataset.start),b=Number(bar.dataset.end);
  if(!Number.isFinite(a)||!Number.isFinite(b)){bar.hidden=true;return}
  const range=extent[1]-extent[0]||1;
  bar.style.left=(a-extent[0])/range*100+'%';
  bar.style.width=(b-a)/range*100+'%';
  if(bar.dataset.tier==='PROVISIONAL'||bar.dataset.tier==='WEAK')bar.style.background='var(--warn)';
});
