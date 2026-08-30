import { useEffect, useMemo, useRef, useState } from 'react';

type Paper = {
  id: string;
  date: string;
  published?: string;
  venue?: string;
  publication_type?: 'Journal' | 'Conference';
  source_detail?: string;
  publication_status?: 'published' | 'preprint' | 'submission';
  title: string;
  abstract?: string;
  url?: string;
  links?: {
    publication?: string;
    arxiv?: string;
    submission?: string;
    card?: string;
  };
  tags: [source: string, topic: string];
};

type MatchMode = 'all' | 'any';
type SortMode = 'published-newest' | 'published-oldest' | 'topic' | 'added-newest' | 'title';
type Theme = 'light' | 'dark';

const FAVORITES_STORAGE_KEY = 'xixi-paper-favorites-v1';

function favoriteKey(paperId: string) {
  return `collection:${paperId}`;
}

function readFavorites(): string[] {
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(FAVORITES_STORAGE_KEY) ?? '[]');
    return Array.isArray(parsed) ? parsed.filter((item): item is string => typeof item === 'string') : [];
  } catch {
    return [];
  }
}

function writeFavorites(favorites: string[]) {
  window.localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify([...new Set(favorites)].sort()));
}

function App() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [query, setQuery] = useState('');
  const [activeTags, setActiveTags] = useState<string[]>([]);
  const [mode, setMode] = useState<MatchMode>('all');
  const [sort, setSort] = useState<SortMode>('published-newest');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [favorites, setFavorites] = useState<string[]>(readFavorites);
  const [favoritesOnly, setFavoritesOnly] = useState(false);
  const [theme, setTheme] = useState<Theme>(() => document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light');
  const importInputRef = useRef<HTMLInputElement>(null);

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
    const sourceCounts = new Map<string, number>();
    const topicCounts = new Map<string, number>();
    papers.forEach((paper) => {
      const [source, topic] = paper.tags;
      sourceCounts.set(source, (sourceCounts.get(source) ?? 0) + 1);
      topicCounts.set(topic, (topicCounts.get(topic) ?? 0) + 1);
    });
    const groups: Record<string, [string, number][]> = {
      Source: [...sourceCounts.entries()],
      Topic: [...topicCounts.entries()],
    };
    groups.Source.sort((a, b) => b[1] - a[1]);
    groups.Topic.sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    return groups;
  }, [papers]);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    return papers
      .filter((paper) => {
        if (favoritesOnly && !favorites.includes(favoriteKey(paper.id))) return false;
        const matchesQuery = !normalized || [paper.title, paper.venue, ...paper.tags]
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
        if (sort === 'topic') {
          return a.tags[1].localeCompare(b.tags[1])
            || (b.published ?? '').localeCompare(a.published ?? '')
            || a.title.localeCompare(b.title);
        }
        if (sort === 'added-newest') return b.date.localeCompare(a.date) || a.title.localeCompare(b.title);
        if (!a.published && !b.published) return a.title.localeCompare(b.title);
        if (!a.published) return 1;
        if (!b.published) return -1;
        const publicationOrder = sort === 'published-newest'
          ? b.published.localeCompare(a.published)
          : a.published.localeCompare(b.published);
        return publicationOrder || a.title.localeCompare(b.title);
      });
  }, [papers, query, activeTags, mode, sort, favorites, favoritesOnly]);

  function toggleTag(tag: string) {
    setActiveTags((current) => current.includes(tag) ? current.filter((item) => item !== tag) : [...current, tag]);
  }

  function clearFilters() {
    setQuery('');
    setActiveTags([]);
    setFavoritesOnly(false);
  }

  function toggleFavorite(paperId: string) {
    const key = favoriteKey(paperId);
    setFavorites((current) => {
      const next = current.includes(key) ? current.filter((item) => item !== key) : [...current, key];
      writeFavorites(next);
      return next;
    });
  }

  function exportFavorites() {
    const payload = JSON.stringify({ version: 1, exported_at: new Date().toISOString(), favorites }, null, 2);
    const url = URL.createObjectURL(new Blob([payload], { type: 'application/json' }));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `xixi-paper-favorites-${new Date().toISOString().slice(0, 10)}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  async function importFavorites(file: File | undefined) {
    if (!file) return;
    try {
      const parsed: unknown = JSON.parse(await file.text());
      const values = Array.isArray(parsed)
        ? parsed
        : typeof parsed === 'object' && parsed !== null && 'favorites' in parsed
          ? (parsed as { favorites: unknown }).favorites
          : null;
      if (!Array.isArray(values) || !values.every((item) => typeof item === 'string')) {
        throw new Error('Invalid favorites file');
      }
      const next = [...new Set([...favorites, ...values])].sort();
      writeFavorites(next);
      setFavorites(next);
    } catch {
      window.alert('无法导入：请选择本站导出的收藏 JSON 文件。');
    } finally {
      if (importInputRef.current) importInputRef.current.value = '';
    }
  }

  function toggleTheme() {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
    document.documentElement.dataset.theme = nextTheme;
    window.localStorage.setItem('paper-collection-xncao-theme', nextTheme);
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
          <h1>Paper Collection-Xncao</h1>
          <p>Xncao&apos;s personal paper collection</p>
        </div>

        <label className="search-box">
          <span className="sr-only">Search papers</span>
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search title, source, or topic…"
          />
        </label>

        <div className="filter-mode">
          <button type="button" className={mode === 'all' ? 'active' : ''} onClick={() => setMode('all')}>Match all tags</button>
          <button type="button" className={mode === 'any' ? 'active' : ''} onClick={() => setMode('any')}>Match any tag</button>
        </div>

        <section className="saved-section" aria-label="收藏与订阅">
          <button type="button" className={favoritesOnly ? 'saved-filter active' : 'saved-filter'} onClick={() => setFavoritesOnly(!favoritesOnly)}>
            ★ 我的收藏 <span>{favorites.filter((item) => item.startsWith('collection:')).length}</span>
          </button>
          <div className="saved-tools">
            <button type="button" onClick={exportFavorites} disabled={favorites.length === 0}>导出</button>
            <button type="button" onClick={() => importInputRef.current?.click()}>导入</button>
            <input ref={importInputRef} className="sr-only" type="file" accept="application/json,.json" onChange={(event) => void importFavorites(event.target.files?.[0])} />
          </div>
          <a className="follow-link" href="./feed.xml">关注更新 · RSS</a>
          <a className="follow-link" href="https://xixi-cc.github.io/daily-article-card/all-feed.xml">全部论文卡 · RSS</a>
        </section>

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
          <strong>Paper Collection-Xncao</strong>
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
            <option value="published-newest">Publication date: newest</option>
            <option value="published-oldest">Publication date: oldest</option>
            <option value="topic">Topic A–Z</option>
            <option value="added-newest">Recently added</option>
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
                <div className="paper-card-header">
                  <h2>
                    {(paper.links?.publication ?? paper.links?.arxiv ?? paper.links?.submission ?? paper.url)
                      ? <a href={paper.links?.publication ?? paper.links?.arxiv ?? paper.links?.submission ?? paper.url} target="_blank" rel="noreferrer">{paper.title}</a>
                      : paper.title}
                  </h2>
                  <button
                    type="button"
                    className={favorites.includes(favoriteKey(paper.id)) ? 'favorite-button active' : 'favorite-button'}
                    onClick={() => toggleFavorite(paper.id)}
                    aria-pressed={favorites.includes(favoriteKey(paper.id))}
                    aria-label={`${favorites.includes(favoriteKey(paper.id)) ? '取消收藏' : '收藏'}：${paper.title}`}
                    title={favorites.includes(favoriteKey(paper.id)) ? '取消收藏' : '收藏'}
                  >
                    {favorites.includes(favoriteKey(paper.id)) ? '★' : '☆'}
                  </button>
                </div>
                <div className="paper-meta">
                  <time title={`Added ${paper.date}`}>
                    {paper.published
                      ? `${paper.publication_status === 'submission' ? 'Submitted' : paper.publication_status === 'preprint' ? 'Posted' : paper.links?.publication ? 'Published' : 'First submitted'} ${paper.published}`
                      : paper.publication_status === 'submission' ? 'Submission date unavailable' : 'Publication date unavailable'}
                  </time>
                  {paper.tags.map((tag) => <button type="button" key={tag} onClick={() => toggleTag(tag)}>{tag}</button>)}
                  {paper.tags[0] === 'Others' && paper.source_detail && <span className="paper-source-detail">{paper.source_detail}</span>}
                  <span className="paper-links">
                    {paper.links?.publication && (
                      <a href={paper.links.publication} target="_blank" rel="noreferrer">
                        {paper.publication_type === 'Conference' ? 'Conference' : paper.publication_type === 'Journal' ? 'Journal' : paper.tags[0] === 'Preprint' ? 'Preprint' : 'Publication'}
                      </a>
                    )}
                    {paper.links?.arxiv && <a href={paper.links.arxiv} target="_blank" rel="noreferrer">arXiv</a>}
                    {paper.links?.submission && <a href={paper.links.submission} target="_blank" rel="noreferrer">OpenReview</a>}
                    {paper.links?.card && <a href={paper.links.card} target="_blank" rel="noreferrer">Paper Card</a>}
                  </span>
                </div>
                {paper.abstract && (
                  <details className="paper-abstract">
                    <summary>Abstract</summary>
                    <p>{paper.abstract}</p>
                  </details>
                )}
              </article>
            ))}
          </div>
        )}
        <footer className="legal-footer">
          <span>© 2026 Xineng Cao · 原创解读 CC BY-NC 4.0</span>
          <a href="./rights.html">许可与引用</a>
        </footer>
      </main>
    </div>
  );
}

export default App;
