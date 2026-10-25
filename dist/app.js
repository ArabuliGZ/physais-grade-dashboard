(() => {
  const data = window.DASHBOARD_DATA;
  const brandLogo = document.querySelector('.brand-mark');
  if (brandLogo?.src) {
    // Repair a single corrupted character in the embedded portable PNG.
    brandLogo.src = brandLogo.src.replace(
      'FoUP1sklV1L+7y3sL5Cb',
      'FoUP1sklV1L+7y3s75Cb'
    );
    const favicon = document.createElement('link');
    favicon.rel = 'icon';
    favicon.type = 'image/png';
    favicon.href = brandLogo.src;
    document.head.appendChild(favicon);
  }
  const palette = {
    ink: '#111827',
    blue: '#e98a3a',
    line: '#e5e7eb',
    paper: '#ffffff',
    grades: { '2':'#c95d5d', '3':'#e3c65d', '4':'#a8bd62', '5':'#4f8b61' }
  };
  const state = { grade: 0, distributionGrade: 0, aiGrade: 0, aiCohortGrade: 0, aiParallelGrade: 8, experimentMetric: 'kr', experimentSample: 'balanced' };
  const allScatterPoints = data.archiveCorrelation.find(item => item.grade === 0)?.points || [];
  const scatterXMax = Math.max(100, Math.ceil(Math.max(...allScatterPoints.map(point => point.x), 100) / 25) * 25);
  const tooltip = document.getElementById('tooltip');
  const homeworkModal = document.getElementById('homework-percent-modal');
  const homeworkModalClose = document.getElementById('homework-percent-close');
  const fmt = (value, digits=2) => value == null ? '—' : Number(value).toFixed(digits).replace('.',',').replace(/^-/,'−');
  const num = value => new Intl.NumberFormat('ru-RU').format(value);
  const yearWord = value => {
    const lastTwo = value % 100, last = value % 10;
    if (lastTwo >= 11 && lastTwo <= 14) return 'лет';
    if (last === 1) return 'год';
    if (last >= 2 && last <= 4) return 'года';
    return 'лет';
  };
  const periodWord = value => {
    const lastTwo = value % 100, last = value % 10;
    if (lastTwo >= 11 && lastTwo <= 14) return 'периодов';
    if (last === 1) return 'период';
    if (last >= 2 && last <= 4) return 'периода';
    return 'периодов';
  };
  const studentWord = value => {
    const lastTwo = value % 100, last = value % 10;
    if (lastTwo >= 11 && lastTwo <= 14) return 'учеников';
    if (last === 1) return 'ученик';
    if (last >= 2 && last <= 4) return 'ученика';
    return 'учеников';
  };

  document.getElementById('stat-years').textContent = num(data.summary.years);
  document.getElementById('stat-groups').textContent = num(data.summary.groups);
  document.getElementById('stat-students').textContent = num(data.summary.students);
  document.getElementById('stat-grades').textContent = num(data.summary.independentGrades);
  document.getElementById('updated-date').textContent = data.generated.split('-').reverse().join('.');

  const svgEl = (name, attrs={}) => {
    const node = document.createElementNS('http://www.w3.org/2000/svg', name);
    Object.entries(attrs).forEach(([key,value]) => node.setAttribute(key,value));
    return node;
  };
  const addText = (svg, text, x, y, cls='axis-label', anchor='middle') => {
    const node = svgEl('text', {x,y,class:cls,'text-anchor':anchor});
    node.textContent = text;
    svg.appendChild(node);
    return node;
  };
  const showTip = (event, html) => {
    tooltip.innerHTML = html;
    tooltip.classList.add('show');
    tooltip.style.left = `${Math.min(event.clientX + 14, window.innerWidth - 245)}px`;
    tooltip.style.top = `${Math.max(8, event.clientY - 60)}px`;
  };
  const hideTip = () => tooltip.classList.remove('show');
  const interactive = (node, html) => {
    node.setAttribute('tabindex','0');
    node.addEventListener('mousemove', event => showTip(event, html));
    node.addEventListener('mouseleave', hideTip);
    node.addEventListener('focus', () => showTip({clientX:window.innerWidth/2,clientY:220}, html));
    node.addEventListener('blur', hideTip);
  };

  function renderArchiveDistribution() {
    const wrap = document.getElementById('archive-distribution-chart');
    wrap.innerHTML = '';
    const distribution = data.distributions.archiveByParallel.find(item => item.grade === state.distributionGrade);
    const checked = data.distributions.checkedByParallel.find(item => item.grade === state.distributionGrade);
    const homeworkGrades = data.distributions.homeworkGradesByParallel.find(item => item.grade === state.distributionGrade);
    const unchecked = data.distributions.uncheckedByParallel.find(item => item.grade === state.distributionGrade);
    const gradeLabel = state.distributionGrade ? `${state.distributionGrade} класс` : 'общая статистика';
    document.getElementById('distribution-title').textContent = `Доля оценок 2–5 · ${gradeLabel}`;
    const compact = window.innerWidth < 620;
    const w = compact ? 640 : 1120, h = 598, left = compact ? 22 : 40, right = compact ? 22 : 40, barH = 64;
    const barWidth = w-left-right;
    const svg = svgEl('svg', {viewBox:`0 0 ${w} ${h}`});

    const makeHomeworkClickable = node => {
      node.classList.add('homework-click-target');
      node.setAttribute('role','button');
      node.setAttribute('tabindex','0');
      node.addEventListener('click', openHomeworkModal);
      node.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          openHomeworkModal();
        }
      });
    };
    const renderBar = ({shares, periods, years, blocks, totalGrades}, y, label, totalLabel, homework=false) => {
      if (homework) {
        const highlight = svgEl('rect', {x:left-12,y:y-38,width:barWidth+24,height:barH+54,class:'homework-highlight'});
        makeHomeworkClickable(highlight);
        svg.appendChild(highlight);
      }
      const barLabel = addText(svg, label, left, y-14, homework ? 'distribution-bar-label homework-label' : 'distribution-bar-label', 'start');
      if (homework) makeHomeworkClickable(barLabel);
      if (periods === 0) {
        svg.appendChild(svgEl('rect', {x:left,y,width:barWidth,height:barH,fill:'none',stroke:palette.line,'stroke-dasharray':'6 5'}));
        addText(svg, 'Периодов без проверки ДЗ нет', left+barWidth/2, y+39, 'distribution-empty');
        return;
      }
      let cursor = left;
      ['2','3','4','5'].forEach(mark => {
        const percent = shares[mark] || 0;
        const width = percent / 100 * barWidth;
        const rect = svgEl('rect', {x:cursor,y,width,height:barH,fill:palette.grades[mark],class:'distribution-segment'});
        interactive(rect, `<strong>${label}</strong><br>Оценка ${mark}: ${fmt(percent,1)}%<br>${totalLabel}<br>Исходных оценок: ${num(totalGrades)}`);
        if (homework) makeHomeworkClickable(rect);
        svg.appendChild(rect);
        const percentLabel = addText(svg, `${fmt(percent,1)}%`, cursor+width/2, y+38, 'distribution-percent');
        percentLabel.setAttribute('fill', '#111827');
        if (homework) makeHomeworkClickable(percentLabel);
        cursor += width;
      });
    };

    renderBar(
      {...distribution, periods:distribution.classYears},
      54,
      'Все периоды',
      `${distribution.classYears} класс-лет`,
    );
    const checkedLabel = checked.periods
      ? `ДЗ проверялось · ${checked.periods} ${periodWord(checked.periods)}`
      : 'ДЗ проверялось';
    renderBar(
      checked,
      198,
      checkedLabel,
      `${checked.years} класс-лет`,
    );
    const homeworkLabel = homeworkGrades.periods
      ? `Оценки за домашнюю работу · ${homeworkGrades.periods} ${periodWord(homeworkGrades.periods)}`
      : 'Оценки за домашнюю работу';
    const inferredHomeworkLabel = homeworkGrades.inferredPeriods
      ? `, включая ${homeworkGrades.inferredPeriods} восстановленных`
      : '';
    renderBar(
      homeworkGrades,
      342,
      homeworkLabel,
      `${homeworkGrades.years} класс-лет с оценками за ДЗ${inferredHomeworkLabel}`,
      true,
    );
    const uncheckedLabel = unchecked.periods
      ? `ДЗ не проверялось · ${unchecked.periods} ${periodWord(unchecked.periods)}`
      : 'ДЗ не проверялось';
    renderBar(
      unchecked,
      486,
      uncheckedLabel,
      `${unchecked.years} полных класс-лет, ${unchecked.blocks} отдельных блока`,
    );
    wrap.appendChild(svg);
  }

  function openHomeworkModal() {
    const entry = data.distributions.homeworkPercentByParallel.find(item => item.grade === state.distributionGrade);
    if (!entry) return;
    const gradeLabel = state.distributionGrade ? `${state.distributionGrade} класс` : 'Все классы';
    document.getElementById('homework-percent-title').textContent = `Выполнение ДЗ по процентам · ${gradeLabel} · ${num(entry.studentYears)} ученико-лет`;
    const wrap = document.getElementById('homework-percent-chart');
    wrap.innerHTML = '<span class="histogram-axis-title">доля ученико-лет</span>';
    const columns = document.createElement('div');
    columns.className = 'histogram-columns';
    const maxShare = Math.max(...entry.bins.map(bin => bin.share), 1);
    entry.bins.forEach(bin => {
      const column = document.createElement('div');
      column.className = 'histogram-column';
      const barWrap = document.createElement('div');
      barWrap.className = 'histogram-bar-wrap';
      const bar = document.createElement('div');
      bar.className = `histogram-bar g${bin.mark}`;
      bar.style.height = `${bin.share / maxShare * 100}%`;
      const value = document.createElement('span');
      value.className = 'histogram-value';
      value.textContent = `${fmt(bin.share,1)}%`;
      bar.appendChild(value);
      interactive(bar, `<strong>${bin.label}% выполнения</strong><br>${fmt(bin.share,1)}% ученико-лет<br>Наблюдений: ${num(bin.count)}<br>Оценка по границе: ${bin.mark}`);
      barWrap.appendChild(bar);
      const label = document.createElement('span');
      label.className = 'histogram-bin-label';
      label.textContent = bin.label;
      column.append(barWrap, label);
      columns.appendChild(column);
    });
    wrap.appendChild(columns);
    homeworkModal.hidden = false;
    document.body.classList.add('modal-open');
    homeworkModalClose.focus();
  }

  function closeHomeworkModal() {
    homeworkModal.hidden = true;
    document.body.classList.remove('modal-open');
    hideTip();
  }

  homeworkModalClose.addEventListener('click', closeHomeworkModal);
  homeworkModal.addEventListener('click', event => {
    if (event.target === homeworkModal) closeHomeworkModal();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !homeworkModal.hidden) closeHomeworkModal();
  });

  function regression(points) {
    if (!points.length) return null;
    const mx = points.reduce((sum,p)=>sum+p.x,0)/points.length;
    const my = points.reduce((sum,p)=>sum+p.y,0)/points.length;
    const denominator = points.reduce((sum,p)=>sum+(p.x-mx)**2,0);
    if (!denominator) return null;
    const slope = points.reduce((sum,p)=>sum+(p.x-mx)*(p.y-my),0)/denominator;
    return {slope, intercept:my-slope*mx};
  }

  function renderScatter() {
    const entry = data.archiveCorrelation.find(item => item.grade===state.grade);
    const wrap = document.getElementById('scatter-chart');
    wrap.innerHTML = '';
    const studentCount = entry?.students || 0;
    document.getElementById('scatter-title').textContent = `${num(studentCount)} ${studentWord(studentCount)} · ${entry?.years || 0} учебных ${yearWord(entry?.years || 0)}`;
    document.getElementById('scatter-r').textContent = fmt(entry?.r,2);
    const legend = document.getElementById('scatter-legend');
    legend.innerHTML = data.archiveCorrelation
      .filter(item => item.grade)
      .map(item => `<span class="${state.grade && state.grade !== item.grade ? 'muted' : ''}"><i class="grade-${item.grade}"></i>${item.grade} класс</span>`)
      .join('');
    if (!entry?.points.length) {
      wrap.innerHTML = '<p class="empty-state">Недостаточно данных для выбранной комбинации.</p>';
      return;
    }
    const compact=window.innerWidth<620;
    const w=compact?760:1100,h=510,m={l:64,r:30,t:28,b:58};
    const xMax=scatterXMax;
    const x=value=>m.l+value/xMax*(w-m.l-m.r),y=value=>m.t+(5.25-value)/3.25*(h-m.t-m.b);
    const svg=svgEl('svg',{viewBox:`0 0 ${w} ${h}`});
    [2,3,4,5].forEach(tick=>{
      svg.appendChild(svgEl('line',{x1:m.l,x2:w-m.r,y1:y(tick),y2:y(tick),class:'grid-line'}));
      addText(svg,String(tick),m.l-15,y(tick)+4,'axis-label','end');
    });
    Array.from({length:xMax/25+1},(_,index)=>index*25).forEach(tick=>{
      svg.appendChild(svgEl('line',{x1:x(tick),x2:x(tick),y1:m.t,y2:h-m.b,class:'grid-line vertical'}));
      addText(svg,`${tick}%`,x(tick),h-25);
    });
    addText(svg,'средняя оценка',m.l,m.t-10,'axis-title','start');
    addText(svg,'выполнено ДЗ',w-m.r,h-5,'axis-title','end');
    const reg=regression(entry.points);
    if(reg) svg.appendChild(svgEl('line',{x1:x(0),y1:y(reg.intercept),x2:x(xMax),y2:y(reg.intercept+reg.slope*xMax),class:'regression-line'}));
    entry.points.forEach(point=>{
      const circle=svgEl('circle',{cx:x(point.x),cy:y(point.y),r:5.4,class:`data-point grade-${point.grade}`});
      interactive(circle,`<strong>${point.year.replace('-', '–')} · ${point.group}</strong><br>ДЗ: ${fmt(point.x,1)}%<br>Средняя оценка: ${fmt(point.y)}<br>Блоков ДЗ: ${point.homeworkCount}<br>Работ: ${point.gradeCount}`);
      svg.appendChild(circle);
    });
    wrap.appendChild(svg);
  }

  const aiBar = (distribution, metricLabel, contextLabel) => {
    const row = document.createElement('div');
    row.className = 'ai-metric';
    const label = document.createElement('span');
    label.className = 'ai-metric-label';
    label.textContent = metricLabel;
    const stack = document.createElement('div');
    stack.className = 'ai-stack';
    ['2','3','4','5'].forEach(mark => {
      const percent = distribution.shares[mark] || 0;
      const segment = document.createElement('span');
      segment.className = `ai-bar-segment g${mark}`;
      segment.style.width = `${percent}%`;
      if (percent >= 9) segment.textContent = `${fmt(percent,1)}%`;
      interactive(segment, `<strong>${contextLabel} · ${metricLabel}</strong><br>Оценка ${mark}: ${fmt(percent,1)}%<br>Исходных оценок: ${num(distribution.totalGrades)}`);
      stack.appendChild(segment);
    });
    row.append(label, stack);
    return row;
  };

  function renderAiImpact() {
    const eraWrap = document.getElementById('ai-era-chart');
    const cohortWrap = document.getElementById('ai-cohort-chart');
    const parallelWrap = document.getElementById('ai-parallel-chart');
    eraWrap.innerHTML = '';
    cohortWrap.innerHTML = '';
    parallelWrap.innerHTML = '';
    const renderComparison = (wrap, entries) => entries.forEach(entry => {
        const card = document.createElement('section');
        card.className = 'ai-era-card';
        const title = document.createElement('h3');
        title.textContent = entry.label;
        card.append(
          title,
          aiBar(entry.homework, 'Оценки за ДЗ', entry.label),
          aiBar(entry.objective, 'Объективные оценки', entry.label),
        );
        wrap.appendChild(card);
      });
    const selectedEras = data.aiImpact.erasByGrade.find(item => item.grade === state.aiGrade);
    renderComparison(eraWrap, selectedEras?.eras || data.aiImpact.eras);
    eraWrap.setAttribute('aria-label', `Распределение оценок до и после появления ИИ · ${selectedEras?.label || '8–9 классы'}`);
    const selectedCohorts = state.aiCohortGrade
      ? data.aiImpact.parallelComparisons.find(item => item.grade === state.aiCohortGrade)?.comparison
      : data.aiImpact.fourCohortComparison;
    renderComparison(cohortWrap, selectedCohorts || data.aiImpact.fourCohortComparison);
    cohortWrap.setAttribute('aria-label', `Среднее распределение оценок · ${state.aiCohortGrade ? `${state.aiCohortGrade} класс` : '8–9 классы'}`);
    data.aiImpact.parallelComparisons
      .filter(parallel => parallel.grade === state.aiParallelGrade)
      .forEach(parallel => {
      const group = document.createElement('section');
      group.className = 'ai-parallel-group';
      const grid = document.createElement('div');
      grid.className = 'ai-era-grid';
      renderComparison(grid, parallel.comparison);
      group.appendChild(grid);
      parallelWrap.appendChild(group);
    });
    parallelWrap.setAttribute('aria-label', `Сравнение ${state.aiParallelGrade} класса с самим собой`);
  }

  const signed = (value, digits=2) => `${value > 0 ? '+' : ''}${fmt(value, digits)}`;
  const experimentColors = { '9Б': '#315a8c', '9Д': '#79569a', neutral: '#374151' };

  function renderExperiment() {
    const compact = window.matchMedia('(max-width:620px)').matches;
    const metric = data.crossoverExperiment.metrics.find(item => item.id === state.experimentMetric);
    const sample = metric.samples.find(item => item.id === state.experimentSample);
    const low = metric.id === 'low';
    const digits = low ? 1 : 2;
    const sampleCounts = sample.students;
    document.getElementById('experiment-sample-count').textContent = state.experimentSample === 'balanced'
      ? `${sampleCounts['9Б'] + sampleCounts['9Д']} учеников · Б: ${sampleCounts['9Б']}, Д: ${sampleCounts['9Д']}`
      : `${sampleCounts['9Б'] + sampleCounts['9Д']} ученика · состав по блокам меняется`;
    document.getElementById('experiment-gap-definition').textContent = low
      ? 'Разрыв = доля двоек в 9Б − доля двоек в 9Д, п.п.'
      : `Разрыв = средняя оценка 9Б − средняя оценка 9Д · ${metric.id === 'kr' ? 'КР' : 'Летучки'}`;

    const wrap = document.getElementById('experiment-gap-chart');
    wrap.innerHTML = '';
    const w = compact ? 760 : 1100, h = 420, left = 70, right = 40, top = 100, bottom = 315;
    const inset = compact ? 45 : 80;
    const x = index => left + inset + index * (w-left-right-2*inset)/4;
    // Preserve the scale when switching between the two student samples.
    const allGaps = metric.samples.flatMap(item => item.timeline.map(row => row.gap));
    const step = low ? 10 : 0.25;
    const lo = Math.floor(Math.min(0, ...allGaps)/step)*step - step;
    const hi = Math.ceil(Math.max(0, ...allGaps)/step)*step + step;
    const y = value => bottom - (value-lo)/(hi-lo)*(bottom-top);
    const svg = svgEl('svg', {viewBox:`0 0 ${w} ${h}`, 'aria-hidden':'true'});
    wrap.setAttribute('aria-label', `${metric.label}. Разрыв Б минус Д: ${sample.timeline.map(row => `блок ${row.block}: ${signed(row.gap,digits)}`).join('; ')}.`);
    for (let tick=lo; tick<=hi+step/10; tick+=step) {
      svg.appendChild(svgEl('line',{x1:left,x2:w-right,y1:y(tick),y2:y(tick),stroke:Math.abs(tick)<1e-8?'#9ca3af':palette.line,'stroke-width':1}));
      addText(svg,signed(Math.abs(tick)<1e-8?0:tick,digits),left-12,y(tick)+5,'experiment-axis','end');
    }
    sample.timeline.forEach((row,index) => {
      const center=x(index), color=row.unchecked?experimentColors[row.unchecked]:experimentColors.neutral;
      if(row.unchecked) svg.appendChild(svgEl('rect',{x:center-76,y:top-10,width:152,height:bottom-top+20,fill:color,opacity:0.055,rx:10}));
      const badgeWidth=compact?132:174;
      svg.appendChild(svgEl('rect',{x:center-badgeWidth/2,y:10,width:badgeWidth,height:62,rx:9,fill:row.unchecked?color:'#f3f4f6',opacity:row.unchecked?0.12:1}));
      addText(svg,row.unchecked?(compact?`${row.unchecked} не сдаёт`:`${row.unchecked} не сдаёт ДЗ`):'Оба сдают ДЗ',center,36,'experiment-phase');
      if(row.unchecked) addText(svg,compact?'ДЗ':row.unchecked==='9Д'?'9Б сдаёт ДЗ':'9Д снова сдаёт ДЗ',center,58,'experiment-phase');
      else addText(svg,compact?(row.block<4?'До опыта':'После опыта'):(row.block<4?'До эксперимента':'После эксперимента'),center,58,'experiment-phase');
      addText(svg,`Блок ${row.block}`,center,365,'experiment-label');
      addText(svg,row.date,center,391,'experiment-axis');
    });
    svg.appendChild(svgEl('line',{x1:left,x2:w-right,y1:y(sample.baselineGap),y2:y(sample.baselineGap),stroke:'#6b7280','stroke-width':2,'stroke-dasharray':'7 6'}));
    svg.appendChild(svgEl('path',{d:sample.timeline.map((row,index)=>`${index?'L':'M'}${x(index)},${y(row.gap)}`).join(' '),fill:'none',stroke:experimentColors.neutral,'stroke-width':3}));
    sample.timeline.forEach((row,index)=>{
      const circle=svgEl('circle',{cx:x(index),cy:y(row.gap),r:8,fill:row.unchecked?experimentColors[row.unchecked]:experimentColors.neutral,stroke:'#fff','stroke-width':3,class:'experiment-gap-point'});
      interactive(circle,`<strong>Блок ${row.block} · ${row.date}</strong><br>Разрыв Б − Д: ${signed(row.gap,digits)} ${metric.unit}<br>Б: ${fmt(row.groups['9Б'].mean,digits)}${low?'%':''} · ${row.groups['9Б'].n} учеников<br>Д: ${fmt(row.groups['9Д'].mean,digits)}${low?'%':''} · ${row.groups['9Д'].n} учеников<br>${row.unchecked?`ДЗ не сдаёт ${row.unchecked}`:'Оба класса сдают ДЗ'}`);
      svg.appendChild(circle);
      addText(svg,signed(row.gap,digits),x(index),y(row.gap)-18,'experiment-value');
    });
    wrap.appendChild(svg);

  }

  function renderExperimentRisk() {
    const wrap=document.getElementById('experiment-risk-chart');
    const svg=svgEl('svg',{viewBox:'0 0 1100 300','aria-hidden':'true'});
    const left=220,right=1045,top=35,bottom=235;
    const x=value=>left+(value+3)/6*(right-left);
    [-3,-2,-1,0,1,2,3].forEach(value=>{
      svg.appendChild(svgEl('line',{x1:x(value),x2:x(value),y1:top,y2:bottom,stroke:value===0?'#9ca3af':palette.line,'stroke-width':value===0?2:1}));
      addText(svg,signed(value,0),x(value),266,'experiment-axis');
    });
    [-0.5,0.5].forEach(value=>svg.appendChild(svgEl('line',{x1:x(value),x2:x(value),y1:top,y2:bottom,stroke:'#9ca3af','stroke-dasharray':'4 5'})));
    data.crossoverExperiment.risk.forEach((row,index)=>{
      const cy=85+index*105,stacks=new Map();
      addText(svg,`${row.group} · блок ${row.block}`,left-24,cy+6,'experiment-label','end');
      row.changes.forEach(change=>{
        const count=stacks.get(change)||0;stacks.set(change,count+1);
        const offset=count===0?0:Math.ceil(count/2)*(count%2?1:-1)*15;
        const dot=svgEl('circle',{cx:x(change),cy:cy+offset,r:6,fill:experimentColors[row.group],opacity:0.8});
        interactive(dot,`${row.group} · блок ${row.block}<br>Изменение относительно другого класса: ${signed(change)} балла`);
        svg.appendChild(dot);
      });
    });
    wrap.replaceChildren(svg);
    document.getElementById('experiment-risk-counts').innerHTML=data.crossoverExperiment.risk.map(row=>`<span><strong>${row.group}: ${row.lower} из ${row.n}</strong> — снижение на 0,5 балла и более</span>`).join('');
  }

  document.querySelectorAll('#experiment-metric-controls button').forEach(button=>button.addEventListener('click',()=>{
    state.experimentMetric=button.dataset.metric;
    document.querySelectorAll('#experiment-metric-controls button').forEach(item=>{item.classList.toggle('active',item===button);item.setAttribute('aria-pressed',String(item===button));});
    renderExperiment();
  }));
  document.querySelectorAll('#experiment-sample-controls button').forEach(button=>button.addEventListener('click',()=>{
    state.experimentSample=button.dataset.sample;
    document.querySelectorAll('#experiment-sample-controls button').forEach(item=>{item.classList.toggle('active',item===button);item.setAttribute('aria-pressed',String(item===button));});
    renderExperiment();
  }));

  document.querySelectorAll('#grade-controls button').forEach(button => button.addEventListener('click',()=>{
    state.grade=Number(button.dataset.grade);
    document.querySelectorAll('#grade-controls button').forEach(item=>item.classList.toggle('active',item===button));
    renderScatter();
  }));
  document.querySelectorAll('#distribution-controls button').forEach(button => button.addEventListener('click',()=>{
    state.distributionGrade=Number(button.dataset.grade);
    document.querySelectorAll('#distribution-controls button').forEach(item=>item.classList.toggle('active',item===button));
    renderArchiveDistribution();
  }));
  document.querySelectorAll('#ai-grade-controls button').forEach(button => button.addEventListener('click',()=>{
    state.aiGrade=Number(button.dataset.grade);
    document.querySelectorAll('#ai-grade-controls button').forEach(item=>item.classList.toggle('active',item===button));
    renderAiImpact();
  }));
  document.querySelectorAll('#ai-cohort-grade-controls button').forEach(button => button.addEventListener('click',()=>{
    state.aiCohortGrade=Number(button.dataset.grade);
    document.querySelectorAll('#ai-cohort-grade-controls button').forEach(item=>item.classList.toggle('active',item===button));
    renderAiImpact();
  }));
  document.querySelectorAll('#ai-parallel-grade-controls button').forEach(button => button.addEventListener('click',()=>{
    state.aiParallelGrade=Number(button.dataset.grade);
    document.querySelectorAll('#ai-parallel-grade-controls button').forEach(item=>item.classList.toggle('active',item===button));
    renderAiImpact();
  }));
  renderArchiveDistribution();
  renderScatter();
  renderAiImpact();
  renderExperiment();
  renderExperimentRisk();
})();
