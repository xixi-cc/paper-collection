import { readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';

const SITE_URL = 'https://xixi-cc.github.io/paper-collection/';
const SOURCE_PATH = resolve('public/papers.json');
const OUTPUT_PATH = resolve('public/feed.xml');

function escapeXml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&apos;');
}

function isoDate(value) {
  const match = String(value ?? '').match(/^\d{4}-\d{2}-\d{2}$/);
  return match ? `${match[0]}T00:00:00Z` : '2026-01-01T00:00:00Z';
}

const papers = JSON.parse(await readFile(SOURCE_PATH, 'utf8'));
// Preserve explicit user removals when older catalogues are imported or synced.
const removals = JSON.parse(await readFile(resolve('data/collection-removals.json'), 'utf8'));
if (removals.schema_version !== 1 || !Array.isArray(removals.paper_ids)
  || !removals.paper_ids.every((id) => typeof id === 'string')
  || new Set(removals.paper_ids).size !== removals.paper_ids.length) {
  throw new Error('Invalid collection removal manifest');
}
const removedIds = new Set(removals.paper_ids);
const restored = papers.filter((paper) => removedIds.has(paper.id)).map((paper) => paper.id);
if (restored.length) {
  throw new Error(`User-removed catalogue entries were reintroduced: ${restored.join(', ')}`);
}

const entries = [...papers]
  .sort((left, right) => String(right.date ?? '').localeCompare(String(left.date ?? '')))
  .slice(0, 80);
const updated = entries.length ? isoDate(entries[0].date) : new Date().toISOString();

const xml = `<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xml:lang="zh-CN">
  <title>Paper Collection-Xncao 更新</title>
  <subtitle>物理、机器学习、机器人与具身智能论文收藏的最新收录。</subtitle>
  <id>${SITE_URL}</id>
  <link href="${SITE_URL}" />
  <link href="${SITE_URL}feed.xml" rel="self" type="application/atom+xml" />
  <updated>${updated}</updated>
  <author><name>Xineng Cao</name><uri>https://xixi-cc.github.io/</uri></author>
${entries.map((paper) => {
  const url = paper.links?.card ?? paper.links?.publication ?? paper.links?.arxiv ?? paper.links?.submission ?? paper.url ?? SITE_URL;
  const source = paper.source_detail ?? paper.tags?.[0] ?? 'Paper Collection';
  const topic = paper.tags?.[1] ?? '';
  return `  <entry>
    <title>${escapeXml(paper.title)}</title>
    <id>urn:xixi-paper:collection:${escapeXml(paper.id)}</id>
    <link href="${escapeXml(url)}" />
    <updated>${isoDate(paper.date)}</updated>
    <summary>${escapeXml([source, topic].filter(Boolean).join(' · '))}</summary>
  </entry>`;
}).join('\n')}
</feed>
`;

await writeFile(OUTPUT_PATH, xml, 'utf8');
console.log(`Generated ${OUTPUT_PATH} with ${entries.length} entries.`);
