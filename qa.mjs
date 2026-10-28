import { chromium } from 'file:///C:/Users/arabu/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/index.mjs';
import { pathToFileURL } from 'node:url';
import path from 'node:path';

const root = process.cwd();
const url = pathToFileURL(path.join(root, 'dist', 'index.html')).href;
const browser = await chromium.launch({
  headless: true,
  executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
});
const results = {};

async function inspect(name, viewport, screenshot) {
  const page = await browser.newPage({ viewport, deviceScaleFactor: 1 });
  const errors = [];
  const interaction = {};
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForFunction(() => document.querySelector('.brand-mark')?.naturalWidth === 70);
  await page.waitForSelector('#archive-distribution-chart svg');
  await page.waitForSelector('#scatter-chart svg');
  await page.waitForSelector('#ai-cohort-chart .ai-era-card');
  await page.waitForSelector('#ai-parallel-chart .ai-era-card');
  await page.waitForSelector('#stopped-analysis .stopped-change-stack');
  await page.waitForSelector('#experiment-gap-chart .experiment-gap-point');
  const rawReading = await page.locator('#stopped-analysis').getAttribute('aria-label');
  const changeStack = page.locator('#stopped-analysis .stopped-change-stack');
  const changeHistogram = page.locator('#stopped-change-histogram');
  interaction.histogramInitiallyHidden = !(await changeHistogram.isVisible());
  await changeStack.hover();
  interaction.histogramOpensOnHover = await changeHistogram.isVisible();
  const rawHistogramAxis = await page.locator('#stopped-change-histogram .stopped-histogram-tick').allTextContents();
  await changeHistogram.screenshot({ path: path.join(root, '..', 'tmp', `physais-change-histogram-${name}.png`) });
  await changeStack.click();
  interaction.histogramOpensOnClick = await changeHistogram.isVisible() &&
    (await changeStack.getAttribute('aria-expanded')) === 'true';
  await changeStack.click();
  interaction.histogramClosesOnClick = !(await changeHistogram.isVisible());
  await page.locator('#stopped-adjustment-controls').getByRole('button', { name: 'С поправкой', exact: true }).click();
  const adjustedReading = await page.locator('#stopped-analysis').getAttribute('aria-label');
  await page.locator('#stopped-analysis .stopped-change-stack').hover();
  const adjustedHistogramAxis = await page.locator('#stopped-change-histogram .stopped-histogram-tick').allTextContents();
  interaction.histogramScaleStable = JSON.stringify(rawHistogramAxis) === JSON.stringify(adjustedHistogramAxis);
  interaction.histogramCountsMatch = await page.evaluate(() => {
    const metric = window.DASHBOARD_DATA.historical.stoppedCheck.metrics[0];
    return metric.changes.reduce((sum, change) => sum + change.count, 0) === metric.n &&
      metric.adjusted.changes.reduce((sum, change) => sum + change.count, 0) === metric.n &&
      metric.histogram.bins.reduce((sum, bin) => sum + bin.count, 0) === metric.n &&
      metric.adjusted.histogram.bins.reduce((sum, bin) => sum + bin.count, 0) === metric.n;
  });
  interaction.stoppedAdjustmentWorks = rawReading.includes('изменение +0,26') && rawReading.includes('снижение более чем на 0,1 у 21') &&
    adjustedReading.includes('изменение +0,36') && adjustedReading.includes('снижение более чем на 0,1 у 16') &&
    (await page.locator('#stopped-adjustment-note').isVisible());
  await page.locator('#checking-stopped').screenshot({ path: path.join(root, '..', 'tmp', `physais-stopped-adjusted-${name}.png`), style: '.topbar{visibility:hidden}' });
  await page.locator('#stopped-adjustment-controls').getByRole('button', { name: 'Без поправки', exact: true }).click();
  const fixedReading = await page.locator('#experiment-gap-chart').getAttribute('aria-label');
  const fixedAxes = await page.locator('#experiment-gap-chart .experiment-axis').allTextContents();
  await page.locator('#experiment-sample-controls').getByRole('button', { name: 'Все писавшие', exact: true }).click();
  const availableReading = await page.locator('#experiment-gap-chart').getAttribute('aria-label');
  const availableAxes = await page.locator('#experiment-gap-chart .experiment-axis').allTextContents();
  interaction.experimentSamplesWork = fixedReading.includes('блок 4: +0,54') && availableReading.includes('блок 4: +0,76');
  interaction.experimentScaleStable = JSON.stringify(fixedAxes) === JSON.stringify(availableAxes);
  await page.locator('#experiment-metric-controls').getByRole('button', { name: 'Доля двоек на КР', exact: true }).click();
  interaction.experimentLowWorks = (await page.locator('#experiment-gap-chart').getAttribute('aria-label')).includes('блок 4: −17,3');
  await page.locator('#experiment-sample-controls').getByRole('button', { name: 'Одни и те же ученики', exact: true }).click();
  await page.locator('#experiment-metric-controls').getByRole('button', { name: 'Летучки', exact: true }).click();
  interaction.experimentQuizWorks = (await page.locator('#experiment-sample-count').textContent()).includes('29 учеников');
  await page.locator('#experiment-metric-controls').getByRole('button', { name: 'Средняя оценка КР', exact: true }).click();
  if (name === 'desktop') {
    await page.locator('#distribution-controls').getByRole('button', { name: '9 класс' }).click();
    const allScale = await page.locator('#scatter-chart .axis-label').allTextContents();
    await page.locator('#grade-controls').getByRole('button', { name: '11 класс' }).click();
    await page.waitForFunction(() => document.querySelectorAll('#scatter-chart circle').length === 47);
    const selectedScale = await page.locator('#scatter-chart .axis-label').allTextContents();
    interaction.scaleStable = JSON.stringify(allScale) === JSON.stringify(selectedScale);
    interaction.selectedLegendItems = await page.locator('#scatter-legend span').count();
    interaction.mutedLegendItems = await page.locator('#scatter-legend span.muted').count();
    await page.locator('#grade-controls').getByRole('button', { name: 'Все классы' }).click();
    await page.waitForFunction(() => document.querySelectorAll('#scatter-chart circle').length === 760);
    await page.waitForFunction(() => document.querySelector('#distribution-title')?.textContent.includes('9 класс'));
    const aiAllWidth = await page.locator('#ai-era-chart .ai-bar-segment').first().evaluate(element => element.style.width);
    await page.locator('#ai-grade-controls').getByRole('button', { name: '8 класс', exact: true }).click();
    const aiEightWidth = await page.locator('#ai-era-chart .ai-bar-segment').first().evaluate(element => element.style.width);
    await page.locator('#ai-grade-controls').getByRole('button', { name: '9 класс', exact: true }).click();
    const aiNineWidth = await page.locator('#ai-era-chart .ai-bar-segment').first().evaluate(element => element.style.width);
    interaction.aiGradeSwitches = aiAllWidth !== aiEightWidth && aiEightWidth !== aiNineWidth;
    interaction.aiActiveGrade = await page.locator('#ai-grade-controls button.active').textContent();
    const cohortAllWidth = await page.locator('#ai-cohort-chart .ai-bar-segment').first().evaluate(element => element.style.width);
    await page.locator('#ai-cohort-grade-controls').getByRole('button', { name: '8 класс', exact: true }).click();
    const cohortEightWidth = await page.locator('#ai-cohort-chart .ai-bar-segment').first().evaluate(element => element.style.width);
    await page.locator('#ai-cohort-grade-controls').getByRole('button', { name: '9 класс', exact: true }).click();
    const cohortNineWidth = await page.locator('#ai-cohort-chart .ai-bar-segment').first().evaluate(element => element.style.width);
    interaction.aiCohortGradeSwitches = cohortAllWidth !== cohortEightWidth && cohortEightWidth !== cohortNineWidth;
    interaction.aiCohortActiveGrade = await page.locator('#ai-cohort-grade-controls button.active').textContent();
    const parallelEightWidth = await page.locator('#ai-parallel-chart .ai-bar-segment').first().evaluate(element => element.style.width);
    await page.locator('#ai-parallel-grade-controls').getByRole('button', { name: '9 класс', exact: true }).click();
    const parallelNineWidth = await page.locator('#ai-parallel-chart .ai-bar-segment').first().evaluate(element => element.style.width);
    interaction.aiParallelGradeSwitches = parallelEightWidth !== parallelNineWidth;
    interaction.aiParallelActiveGrade = await page.locator('#ai-parallel-grade-controls button.active').textContent();
  }
  results[name] = {...await page.evaluate(() => ({
    title: document.title,
    faviconPresent: Boolean(document.querySelector('link[rel="icon"]')?.href.startsWith('data:image/png;base64,')),
    brandLogoLoaded: document.querySelector('.brand-mark')?.naturalWidth === 70,
    experimentStudents: document.querySelector('#experiment-sample-count')?.textContent,
    experimentGapPoints: document.querySelectorAll('#experiment-gap-chart .experiment-gap-point').length,
    scatterTitle: document.querySelector('#scatter-title')?.textContent,
    distributionTitle: document.querySelector('#distribution-title')?.textContent,
    charts: document.querySelectorAll('svg').length,
    classRows: document.querySelectorAll('#archive-distribution-chart .class-label').length,
    distributionRects: document.querySelectorAll('#archive-distribution-chart rect').length,
    distributionSegments: document.querySelectorAll('#archive-distribution-chart .distribution-segment').length,
    homeworkHighlights: document.querySelectorAll('#archive-distribution-chart .homework-highlight').length,
    homeworkPeriodsMatch: window.DASHBOARD_DATA.distributions.checkedByParallel.every(item =>
      window.DASHBOARD_DATA.distributions.homeworkGradesByParallel.find(other => other.grade === item.grade)?.periods === item.periods
    ),
    inferredHomeworkPeriods: window.DASHBOARD_DATA.distributions.homeworkGradesByParallel.find(item => item.grade === 0)?.inferredPeriods,
    points: document.querySelectorAll('#scatter-chart circle').length,
    pointGrades: [...new Set([...document.querySelectorAll('#scatter-chart circle')].map(point => point.classList[1]))].length,
    legendItems: document.querySelectorAll('#scatter-legend span').length,
    aiEraCards: document.querySelectorAll('#ai-era-chart .ai-era-card').length,
    aiGradeControls: document.querySelectorAll('#ai-grade-controls button').length,
    aiCohortGradeControls: document.querySelectorAll('#ai-cohort-grade-controls button').length,
    aiCohortCards: document.querySelectorAll('#ai-cohort-chart .ai-era-card').length,
    aiParallelCards: document.querySelectorAll('#ai-parallel-chart .ai-era-card').length,
    aiParallelGroups: document.querySelectorAll('#ai-parallel-chart .ai-parallel-group').length,
    aiParallelGradeControls: document.querySelectorAll('#ai-parallel-grade-controls button').length,
    aiStacks: document.querySelectorAll('#ai-impact .ai-stack').length,
    aiSegments: document.querySelectorAll('#ai-impact .ai-bar-segment').length,
    stoppedPopulation: document.querySelector('#stopped-policy-population')?.textContent,
    stoppedTransitionCards: document.querySelectorAll('#stopped-analysis .stopped-transition-card').length,
    stoppedChangeSegments: document.querySelectorAll('#stopped-analysis .stopped-change-segment').length,
    groups: document.querySelector('#stat-groups')?.textContent,
    homeworkStatPresent: Boolean(document.querySelector('#stat-homework')),
    overflow: document.documentElement.scrollWidth - window.innerWidth,
    height: document.documentElement.scrollHeight,
  })), ...interaction};
  results[name].errors = errors;
  await page.screenshot({ path: screenshot, fullPage: true });
  await page.locator('.topbar').screenshot({ path: path.join(root, '..', 'tmp', `physais-topbar-${name}.png`) });
  await page.locator('#distribution').screenshot({ path: path.join(root, '..', 'tmp', `physais-distribution-${name}.png`) });
  await page.locator('#correlation').screenshot({ path: path.join(root, '..', 'tmp', `physais-correlation-${name}.png`) });
  await page.locator('#ai-impact').screenshot({ path: path.join(root, '..', 'tmp', `physais-ai-${name}.png`) });
  await page.locator('#checking-stopped').screenshot({ path: path.join(root, '..', 'tmp', `physais-stopped-${name}.png`), style: '.topbar{visibility:hidden}' });
  await page.locator('#homework-experiment').screenshot({ path: path.join(root, '..', 'tmp', `physais-experiment-${name}.png`), style: '.topbar{visibility:hidden}' });
  await page.locator('.experiment-details summary').click();
  await page.locator('.experiment-details').screenshot({ path: path.join(root, '..', 'tmp', `physais-experiment-risk-${name}.png`) });
  await page.locator('.experiment-details summary').click();
  await page.locator('#archive-distribution-chart .distribution-percent.homework-click-target').first().evaluate(element => {
    element.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  });
  await page.waitForSelector('#homework-percent-modal:not([hidden])');
  results[name].histogramBars = await page.locator('#homework-percent-chart .histogram-bar').count();
  results[name].histogramTitle = await page.locator('#homework-percent-title').textContent();
  results[name].modalVisible = await page.locator('#homework-percent-modal').isVisible();
  await page.locator('.chart-modal-card').screenshot({ path: path.join(root, '..', 'tmp', `physais-homework-modal-${name}.png`) });
  await page.locator('#homework-percent-close').click();
  results[name].modalClosed = await page.locator('#homework-percent-modal').isVisible() === false;
  await page.close();
}

await inspect('desktop', { width: 1440, height: 1000 }, path.join(root, '..', 'tmp', 'physais-site-desktop.png'));
await inspect('mobile', { width: 390, height: 844 }, path.join(root, '..', 'tmp', 'physais-site-mobile.png'));
await browser.close();

const failed = Object.values(results).some(result =>
  result.errors.length || !result.faviconPresent || !result.brandLogoLoaded || result.charts < 2 || result.classRows !== 0 ||
  !result.experimentSamplesWork || !result.experimentScaleStable || !result.experimentLowWorks || !result.experimentQuizWorks ||
  result.experimentGapPoints !== 5 || !result.experimentStudents.includes('40 учеников') ||
  result.distributionSegments !== 16 || result.homeworkHighlights !== 1 || !result.homeworkPeriodsMatch || result.inferredHomeworkPeriods !== 2 || result.points < 1 || result.pointGrades < 1 || result.groups !== '21' ||
  result.aiEraCards !== 2 || result.aiGradeControls !== 3 || result.aiCohortGradeControls !== 3 || result.aiCohortCards !== 2 || result.aiParallelCards !== 2 || result.aiParallelGroups !== 1 || result.aiParallelGradeControls !== 2 || result.aiStacks !== 12 || result.aiSegments !== 48 ||
  !result.stoppedAdjustmentWorks || !result.histogramInitiallyHidden || !result.histogramOpensOnHover ||
  !result.histogramOpensOnClick || !result.histogramClosesOnClick || !result.histogramScaleStable || !result.histogramCountsMatch ||
  !result.stoppedPopulation?.includes('116') || result.stoppedTransitionCards !== 3 || result.stoppedChangeSegments !== 5 ||
  result.histogramBars !== 12 || !result.modalVisible || !result.modalClosed ||
  result.homeworkStatPresent || result.overflow > 1
);
if (Object.values(results).some(result => result.legendItems !== 5 || result.pointGrades !== 5)) process.exitCode = 1;
if (!results.desktop.scaleStable || results.desktop.selectedLegendItems !== 5 || results.desktop.mutedLegendItems !== 4) process.exitCode = 1;
if (!results.desktop.aiGradeSwitches || results.desktop.aiActiveGrade?.trim() !== '9 класс') process.exitCode = 1;
if (!results.desktop.aiCohortGradeSwitches || results.desktop.aiCohortActiveGrade?.trim() !== '9 класс') process.exitCode = 1;
if (!results.desktop.aiParallelGradeSwitches || results.desktop.aiParallelActiveGrade?.trim() !== '9 класс') process.exitCode = 1;
console.log(JSON.stringify(results, null, 2));
if (failed) process.exitCode = 1;
