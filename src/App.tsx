import { useEffect, useMemo, useState } from 'react';

type Paper = {
  id: string;
  date: string;
  title: string;
  url: string;
  tags: string[];
};

type MatchMode = 'all' | 'any';
type SortMode = 'newest' | 'oldest' | 'title';
type Theme = 'light' | 'dark';

const SOURCE_TAGS = new Set(['arXiv', 'OpenReview', 'Journal', 'Conference']);

function tagGroup(tag: string) {
  if (SOURCE_TAGS.has(tag)) return 'Source';
  if (/^20\d{2}-\d{2}$/.test(tag)) return 'Month';
  return 'Topic';
}

function App() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [query, setQuery] = useState('');
  const [activeTags, setActiveTags] = useState<string[]>([]);
  const [mode, setMode] = useState<MatchMode>('all');
  const [sort, setSort] = useState<SortMode>('newest');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [theme, setTheme] = useState<Theme>(() => document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light');

  useEffect(() => {
    fetch('./papers.json')
      .then((response) => {
        if (!response.ok) throw new Error('Failed to load papers');
        return response.json() as Promise<Paper[]>;
      })
      .then(setPapers)
      .catch(() => setLoadError(true));
  }, []);

  const tagGroups = useMemo(() => {
    const counts = new Map<string, number>();
    papers.forEach((paper) => paper.tags.forEach((tag) => counts.set(tag, (counts.get(tag) ?? 0) + 1)));
    const groups: Record<string, [string, number][]> = { Source: [], Month: [], Topic: [] };
    counts.forEach((count, tag) => groups[tagGroup(tag)].push([tag, count]));
    groups.Source.sort((a, b) => b[1] - a[1]);
    groups.Month.sort((a, b) => b[0].localeCompare(a[0]));
    groups.Topic.sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    return groups;
  }, [papers]);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    return papers
      .filter((paper) => {
        const matchesQuery = !normalized || [paper.title, ...paper.tags]
          .filter(Boolean)
          .join(' ')
          .toLocaleLowerCase()
          .includes(normalized);
        const matchesTags = activeTags.length === 0 || (mode === 'all'
          ? activeTags.every((tag) => paper.tags.includes(tag))
          : activeTags.some((tag) => paper.tags.includes(tag)));
        return matchesQuery && matchesTags;
      })
      .sort((a, b) => {
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

  function toggleTheme() {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
    window.localStorage.setItem('paper-collection-theme', nextTheme);
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', nextTheme === 'dark' ? '#0f1419' : '#f0f1ef');
  }

  return (
    <div className="layout">
      <aside className={`sidebar ${filtersOpen ? 'open' : ''}`}>
        <div className="sidebar-top">
          <a className="back-home" href="https://github.com/xixi-cc" target="_blank" rel="noreferrer">← GitHub profile</a>
          <button className="theme-toggle" type="button" onClick={toggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
            {theme === 'dark' ? 'Light' : 'Dark'}
          </button>
        </div>

        <div className="brand">
          <h1>Paper Collection</h1>
          <p>Xixi&apos;s personal paper collection</p>
        </div>

        <label className="search-box">
          <span className="sr-only">Search papers</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search title or tags…"
          />
        </label>

        <div className="filter-mode">
          <button type="button" className={mode === 'all' ? 'active' : ''} onClick={() => setMode('all')}>Match all tags</button>
          <button type="button" className={mode === 'any' ? 'active' : ''} onClick={() => setMode('any')}>Match any tag</button>
        </div>

        {Object.entries(tagGroups).map(([group, tags]) => (
          <section className="tag-section" key={group}>
            <h2>{group}</h2>
            <div className="tag-list">
              {tags.map(([tag, count]) => (
                <button type="button" key={tag} className={activeTags.includes(tag) ? 'active' : ''} onClick={() => toggleTag(tag)}>
                  {tag} <span>{count}</span>
                </button>
              ))}
            </div>
          </section>
        ))}

        <button type="button" className="clear-filters" onClick={clearFilters}>Clear all filters</button>
      </aside>

      <main className="main">
        <div className="mobile-bar">
          <strong>Paper Collection</strong>
          <div className="mobile-actions">
            <button type="button" onClick={toggleTheme} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
              {theme === 'dark' ? 'Light' : 'Dark'}
            </button>
            <button type="button" onClick={() => setFiltersOpen(!filtersOpen)} aria-expanded={filtersOpen}>Filters</button>
          </div>
        </div>

        <div className="stats-bar">
          <p>Showing <strong>{filtered.length}</strong> of <strong>{papers.length}</strong> papers</p>
          <select value={sort} onChange={(event) => setSort(event.target.value as SortMode)} aria-label="Sort papers">
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="title">Title A–Z</option>
          </select>
        </div>

        {loadError ? (
          <div className="empty-state">Failed to load the paper list.</div>
        ) : filtered.length === 0 ? (
          <div className="empty-state">No papers have been added yet.</div>
        ) : (
          <div className="paper-list">
            {filtered.map((paper) => (
              <article className="paper-card" key={paper.id}>
                <h2><a href={paper.url} target="_blank" rel="noreferrer">{paper.title}</a></h2>
                <div className="paper-meta">
                  <time>{paper.date}</time>
                  {paper.tags.map((tag) => <button type="button" key={tag} onClick={() => toggleTag(tag)}>{tag}</button>)}
                </div>
              </article>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
