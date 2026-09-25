(function(){
  var css = document.createElement('style');
  css.textContent = [
    '#ci-root{font:13px/1.5 var(--font,system-ui);color:var(--foreground);max-width:720px;margin-bottom:1.5rem}',
    '#ci-root .stats{display:flex;gap:1.25rem;flex-wrap:wrap;margin:.5rem 0 .25rem}',
    '#ci-root .stat b{font-size:1.25rem;display:block}',
    '#ci-root .stat span{color:var(--muted-foreground);font-size:.8rem}',
    '#ci-root .bars{display:flex;align-items:flex-end;gap:2px;height:110px;margin:.75rem 0 .25rem}',
    '#ci-root .bar{flex:1;display:flex;flex-direction:column;justify-content:flex-end;min-width:3px}',
    '#ci-root .bar:hover .s{filter:brightness(1.25)}',
    '#ci-root .bar .s{background:var(--accent);border-radius:1px 1px 0 0}',
    '#ci-root .bar .f{background:var(--border)}',
    '#ci-root .xl{display:flex;gap:2px;color:var(--muted-foreground);font-size:.65rem}',
    '#ci-root .xl span{flex:1;text-align:center;min-width:3px;white-space:nowrap}',
    '#ci-root .legend{color:var(--muted-foreground);font-size:.75rem;margin-top:.5rem}',
    '#ci-root .dot{display:inline-block;width:8px;height:8px;border-radius:2px;vertical-align:middle;margin:0 4px 0 10px}',
    '#ci-root [data-tip]{position:relative;cursor:help}',
    '#ci-root [data-tip]:hover::after{content:attr(data-tip);position:absolute;bottom:calc(100% + 6px);left:0;z-index:9;background:var(--foreground);color:var(--background);padding:.4rem .6rem;border-radius:6px;font-size:.72rem;line-height:1.45;white-space:normal;width:max-content;max-width:240px;pointer-events:none;box-shadow:0 4px 12px rgba(0,0,0,.18)}'
  ].join('\n');
  document.head.appendChild(css);
  var MONTHS=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  function pretty(l){ var p=l.split('-'); if(p.length<2) return l; var m=+p[1]; return (MONTHS[m-1]||'?')+' '+(+p[2]||p[1]); }
  fetch('ci-activity-data.json').then(r=>r.json()).then(function(d){
    var labels=d.labels, counts=d.counts, succ=d.succ, stats=d.stats;
    var max = Math.max.apply(null, counts.concat([1]));
    function bar(c,s,i){ if(!c) return '<div class="bar"></div>';
      var f=c-s;
      var tip=pretty(labels[i])+' — '+c+' run'+(c===1?'':'s')+' · '+s+' passed'+(f?' · '+f+' failed/canceled':'');
      return '<div class="bar" data-tip="'+tip+'">'
      + '<div class="s" style="height:'+(s/max*100).toFixed(1)+'%"></div>'
      + '<div class="f" style="height:'+(f/max*100).toFixed(1)+'%"></div></div>'; }
    var root = document.getElementById('ci-root');
    root.innerHTML =
      '<div class="stats">'
      + '<div class="stat" data-tip="Every pipeline run across merge requests, dev pushes, and gated prod deploys — Sep 4–23, 2026, straight from the GitLab API."><b>'+stats.total+'</b><span>CI runs &middot; 20 days</span></div>'
      + '<div class="stat" data-tip="475 of 548 runs passed. Failures are not hidden — they fail the MR before it can merge or deploy. That is the gate working."><b>'+stats.success_rate+'%</b><span>pass rate</span></div>'
      + '<div class="stat" data-tip="Half of all pipelines complete in under 1.6 min — fast feedback on every push keeps the loop tight."><b>'+stats.median_min+' min</b><span>median pipeline</span></div>'
      + '<div class="stat" data-tip="Production never moves automatically: deploys are manual and only runnable after every security scanner passed on that exact commit SHA."><b>'+stats.main_runs+'</b><span>prod deploys (gated)</span></div>'
      + '<div class="stat" data-tip="Every merge request runs the full gate — ruff, pytest, docker build, and four security scanners — before it can merge."><b>'+stats.mr_runs+'</b><span>MR pipelines</span></div>'
      + '</div>'
      + '<div class="bars">'+labels.map(function(_,i){return bar(counts[i],succ[i],i);}).join('')+'</div>'
      + '<div class="xl">'+labels.map(function(l,i){return i%4===0?'<span>'+l+'</span>':'<span></span>';}).join('')+'</div>'
      + '<div class="legend"><span class="dot" style="background:var(--accent)"></span>passed'
      + '<span class="dot" style="background:var(--border)"></span>failed/canceled &mdash; every MR, dev push, and prod deploy ran the full gate: ruff &middot; pytest &middot; docker build &middot; secrets-scan &middot; config-scan &middot; deps-audit &middot; image-scan</div>';
  });
})();
