import { useEffect, useMemo, useState } from 'react';

type Paper = {
  id: string;
  date: string;
  title: string;
  titleZh: string;
  url: string;
  note: string;
  details: string;
  readingMinutes: number;
  tags: string[];
};

type MatchMode = 'all' | 'any';
type SortMode = 'newest' | 'oldest' | 'title';

const SOURCE_TAGS = new Set(['arXiv', 'OpenReview', '期刊', '会议']);

function tagGroup(tag: string) {
  if (SOURCE_TAGS.has(tag)) return '来源';
  if (/^20\d{2}-\d{2}$/.test(tag)) return '时间';
  return '主题';
}

function App() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [query, setQuery] = useState('');
  const [activeTags, setActiveTags] = useState<string[]>([]);
  const [mode, setMode] = useState<MatchMode>('all');
  const [sort, setSort] = useState<SortMode>('newest');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    fetch('./papers.json')
      .then((response) => {
        if (!response.ok) throw new Error('无法读取文章数据');
        return response.json() as Promise<Paper[]>;
      })
      .then(setPapers)
      .catch(() => setLoadError(true));
  }, []);

  const tagGroups = useMemo(() => {
    const counts = new Map<string, number>();
    papers.forEach((paper) => paper.tags.forEach((tag) => counts.set(tag, (counts.get(tag) ?? 0) + 1)));
    const groups: Record<string, [string, number][]> = { 来源: [], 时间: [], 主题: [] };
    counts.forEach((count, tag) => groups[tagGroup(tag)].push([tag, count]));
    groups.来源.sort((a, b) => b[1] - a[1]);
    groups.时间.sort((a, b) => b[0].localeCompare(a[0]));
    groups.主题.sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    return groups;
  }, [papers]);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    const result = papers.filter((paper) => {
      const matchesQuery = !normalized || [paper.title, paper.titleZh, paper.note, paper.details, ...paper.tags]
        .join(' ')
        .toLocaleLowerCase()
        .includes(normalized);
      const matchesTags = activeTags.length === 0 || (mode === 'all'
        ? activeTags.every((tag) => paper.tags.includes(tag))
        : activeTags.some((tag) => paper.tags.includes(tag)));
      return matchesQuery && matchesTags;
    });
    return result.sort((a, b) => {
      if (sort === 'title') return a.title.localeCompare(b.title);
      return sort === 'newest' ? b.date.localeCompare(a.date) : a.date.localeCompare(b.date);
    });
  }, [papers, query, activeTags, mode, sort]);

  function toggleTag(tag: string) {
    setActiveTags((current) => current.includes(tag) ? current.filter((item) => item !== tag) : [...current, tag]);
  }

  function clearFilters() {
    setQuery('');
    setActiveTags([]);
  }

  return (
    <div className="site-shell" id="top">
      <header className="masthead">
        <a className="identity" href="./" aria-label="返回论文收藏首页">
          <span className="identity-mark" aria-hidden="true">XC</span>
          <span><strong>Xixi&apos;s Library</strong><small>Research, annotated.</small></span>
        </a>
        <a className="github-link" href="https://github.com/xixi-cc" target="_blank" rel="noreferrer">
          GitHub <span aria-hidden="true">↗</span>
        </a>
      </header>

      <section className="hero">
        <p className="eyebrow"><span /> PERSONAL PAPER INDEX · 2026</p>
        <h1>从噪声里，<em>留下值得细读的文章。</em></h1>
        <p className="hero-copy">物理 × 人工智能 × 复杂系统。这里不是论文堆积，而是我持续整理、筛选和重读的个人研究地图。</p>
        <div className="hero-stats" aria-label="收藏统计">
          <span><strong>{papers.length || '—'}</strong> 篇收录</span>
          <span><strong>{tagGroups.主题.length || '—'}</strong> 个主题</span>
          <span><strong>持续</strong> 更新</span>
        </div>
      </section>

      <div className="search-row">
        <label className="search-box">
          <span aria-hidden="true">⌕</span>
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索标题、主题或笔记…" />
          {query && <button type="button" onClick={() => setQuery('')} aria-label="清空搜索">×</button>}
        </label>
        <button className="filter-toggle" type="button" onClick={() => setFiltersOpen(!filtersOpen)} aria-expanded={filtersOpen}>
          筛选 {activeTags.length > 0 && <b>{activeTags.length}</b>}
        </button>
      </div>

      <main className="collection-layout">
        <aside className={`filters ${filtersOpen ? 'open' : ''}`}>
          <div className="filter-heading"><h2>筛选文章</h2><button type="button" onClick={clearFilters}>全部清除</button></div>
          <div className="match-mode" aria-label="标签匹配方式">
            <button className={mode === 'all' ? 'active' : ''} onClick={() => setMode('all')}>同时满足</button>
            <button className={mode === 'any' ? 'active' : ''} onClick={() => setMode('any')}>满足任一</button>
          </div>
          {Object.entries(tagGroups).map(([group, tags]) => tags.length > 0 && (
            <section className="tag-section" key={group}>
              <h3>{group}</h3>
              <div className="tag-list">
                {tags.map(([tag, count]) => (
                  <button key={tag} className={activeTags.includes(tag) ? 'active' : ''} onClick={() => toggleTag(tag)}>
                    <span>{tag}</span><small>{count}</small>
                  </button>
                ))}
              </div>
            </section>
          ))}
        </aside>

        <section className="results" aria-live="polite">
          <div className="results-bar">
            <p><strong>{filtered.length}</strong> / {papers.length} 篇文章</p>
            <label>排序
              <select value={sort} onChange={(event) => setSort(event.target.value as SortMode)}>
                <option value="newest">最新收录</option>
                <option value="oldest">最早收录</option>
                <option value="title">英文标题 A–Z</option>
              </select>
            </label>
          </div>

          {loadError ? <div className="empty-state">文章数据暂时无法加载，请稍后刷新。</div> : filtered.length === 0 && papers.length > 0 ? (
            <div className="empty-state"><strong>没有找到匹配的文章。</strong><button type="button" onClick={clearFilters}>清除筛选条件</button></div>
          ) : (
            <div className="paper-list">
              {filtered.map((paper, index) => (
                <article className="paper-card" key={paper.id}>
                  <div className="paper-index">{String(index + 1).padStart(2, '0')}</div>
                  <div className="paper-body">
                    <div className="paper-topline"><time>{paper.date}</time><span>{paper.readingMinutes} MIN READ</span></div>
                    <h2><a href={paper.url} target="_blank" rel="noreferrer">{paper.titleZh}</a></h2>
                    <p className="english-title">{paper.title}</p>
                    <p className="paper-note">{paper.note}</p>
                    <div className="paper-footer">
                      <div>{paper.tags.slice(0, 4).map((tag) => <button key={tag} onClick={() => toggleTag(tag)}>{tag}</button>)}</div>
                      <a href={paper.url} target="_blank" rel="noreferrer" aria-label={`阅读 ${paper.titleZh}`}>阅读全文 <span aria-hidden="true">↗</span></a>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </main>

      <footer><span>XIXI&apos;S PAPER COLLECTION</span><p>Curated with curiosity · Hosted on GitHub Pages</p><a href="#top">回到顶部 ↑</a></footer>
    </div>
  );
}

export default App;
