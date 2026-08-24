import { useEffect, useMemo, useState } from 'react';

type Paper = {
  id: string;
  date: string;
  published?: string;
  venue?: string;
  publication_type?: 'Journal' | 'Conference';
  source_detail?: string;
  publication_status?: 'published' | 'preprint' | 'submission';
  title: string;
  url?: string;
  links?: {
    publication?: string;
    arxiv?: string;
    submission?: string;
  };
  tags: [source: string, topic: string];
};

type MatchMode = 'all' | 'any';
type SortMode = 'published-newest' | 'published-oldest' | 'topic' | 'added-newest' | 'title';
type Theme = 'light' | 'dark';
type ViewMode = 'review' | 'browse';

const PAGE_SIZE = 10;
const REVIEW_SESSION_KEY = 'paper-collection-review-session';

type ReviewRecord = {
  selectedIds: string[];
  currentPage: number;
  totalPapers: number;
  completed: boolean;
  updatedAt: string;
  completedAt?: string | null;
};

function App() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [query, setQuery] = useState('');
  const [activeTags, setActiveTags] = useState<string[]>([]);
  const [mode, setMode] = useState<MatchMode>('all');
  const [sort, setSort] = useState<SortMode>('published-newest');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [theme, setTheme] = useState<Theme>(() => document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light');
  const [view, setView] = useState<ViewMode>('review');
  const [reviewPage, setReviewPage] = useState(0);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [reviewReady, setReviewReady] = useState(false);
  const [reviewCompleted, setReviewCompleted] = useState(false);
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [sessionId] = useState(() => {
    const stored = window.localStorage.getItem(REVIEW_SESSION_KEY);
    if (stored) return stored;
    const created = crypto.randomUUID();
    window.localStorage.setItem(REVIEW_SESSION_KEY, created);
    return created;
  });

  useEffect(() => {
    fetch('./papers.json')
      .then((response) => {
        if (!response.ok) throw new Error('Failed to load papers');
        return response.json() as Promise<Paper[]>;
      })
      .then(setPapers)
      .catch(() => setLoadError(true));
  }, []);

  useEffect(() => {
    if (papers.length === 0) return;
    fetch(`/api/review?session=${encodeURIComponent(sessionId)}`)
      .then((response) => {
        if (!response.ok) throw new Error('Failed to load review');
        return response.json() as Promise<ReviewRecord | null>;
      })
      .then((record) => {
        if (record) {
          setSelectedIds(record.selectedIds.filter((id) => papers.some((paper) => paper.id === id)));
          setReviewPage(Math.min(record.currentPage, Math.max(0, Math.ceil(papers.length / PAGE_SIZE) - 1)));
          setReviewCompleted(record.completed);
        }
        setReviewReady(true);
      })
      .catch(() => {
        setReviewReady(true);
        setSaveState('error');
      });
  }, [papers, sessionId]);

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
  }, [papers, query, activeTags, mode, sort]);

  const reviewPapers = useMemo(() => papers.slice(
    reviewPage * PAGE_SIZE,
    reviewPage * PAGE_SIZE + PAGE_SIZE,
  ), [papers, reviewPage]);
  const pageCount = Math.ceil(papers.length / PAGE_SIZE);

  async function saveReview(nextSelectedIds: string[], nextPage: number, completed = false) {
    setSaveState('saving');
    try {
      const response = await fetch('/api/review', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          sessionId,
          selectedIds: nextSelectedIds,
          currentPage: nextPage,
          totalPapers: papers.length,
          completed,
        }),
      });
      if (!response.ok) throw new Error('Failed to save review');
      setSaveState('saved');
      return true;
    } catch {
      setSaveState('error');
      return false;
    }
  }

  function toggleDislike(paperId: string) {
    if (reviewCompleted) return;
    const next = selectedIds.includes(paperId)
      ? selectedIds.filter((id) => id !== paperId)
      : [...selectedIds, paperId];
    setSelectedIds(next);
    void saveReview(next, reviewPage);
  }

  async function moveToPage(nextPage: number) {
    if (nextPage < 0 || nextPage >= pageCount) return;
    const saved = await saveReview(selectedIds, nextPage);
    if (!saved) return;
    setReviewPage(nextPage);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async function completeReview() {
    const saved = await saveReview(selectedIds, reviewPage, true);
    if (!saved) return;
    setReviewCompleted(true);
    setConfirmOpen(false);
  }

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

        <div className="view-switch" role="group" aria-label="Choose paper collection mode">
          <button type="button" className={view === 'review' ? 'active' : ''} onClick={() => setView('review')}>筛选论文</button>
          <button type="button" className={view === 'browse' ? 'active' : ''} onClick={() => setView('browse')}>浏览收藏</button>
        </div>

        {view === 'review' ? (
          <section className="review-workspace" aria-labelledby="review-title">
            <header className="review-header">
              <div>
                <p className="eyebrow">COLLECTION REVIEW</p>
                <h2 id="review-title">勾选你不喜欢的论文</h2>
                <p>每页 10 篇。你的选择会自动保存；完成前不会删除任何论文。</p>
              </div>
              <div className="review-count" aria-live="polite">
                <strong>{selectedIds.length}</strong>
                <span>篇待删除</span>
              </div>
            </header>

            {reviewCompleted ? (
              <div className="review-complete">
                <span className="complete-mark" aria-hidden="true">✓</span>
                <div>
                  <h3>筛选已完成</h3>
                  <p>已提交 {selectedIds.length} 篇不喜欢的论文。名单现已锁定，论文尚未从网站删除。</p>
                </div>
              </div>
            ) : !reviewReady ? (
              <div className="empty-state">正在载入你的筛选进度…</div>
            ) : (
              <>
                <div className="review-progress" aria-label={`第 ${reviewPage + 1} 页，共 ${pageCount} 页`}>
                  <div className="progress-copy">
                    <span>第 {reviewPage + 1} / {pageCount} 页</span>
                    <span>论文 {reviewPage * PAGE_SIZE + 1}–{Math.min((reviewPage + 1) * PAGE_SIZE, papers.length)} / {papers.length}</span>
                  </div>
                  <div className="progress-track"><span style={{ width: `${((reviewPage + 1) / pageCount) * 100}%` }} /></div>
                </div>

                <div className="review-list">
                  {reviewPapers.map((paper, index) => {
                    const selected = selectedIds.includes(paper.id);
                    const href = paper.links?.publication ?? paper.links?.arxiv ?? paper.links?.submission ?? paper.url;
                    return (
                      <label className={`review-card ${selected ? 'selected' : ''}`} key={paper.id}>
                        <input type="checkbox" checked={selected} onChange={() => toggleDislike(paper.id)} />
                        <span className="review-checkbox" aria-hidden="true">{selected ? '✓' : ''}</span>
                        <span className="paper-number">{reviewPage * PAGE_SIZE + index + 1}</span>
                        <span className="review-paper-content">
                          <span className="review-paper-title">
                            {href ? <a href={href} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}>{paper.title}</a> : paper.title}
                          </span>
                          <span className="review-paper-meta">
                            <span>{paper.published ?? '日期未知'}</span>
                            {paper.tags.map((tag) => <span className="review-tag" key={tag}>{tag}</span>)}
                          </span>
                        </span>
                        <span className="dislike-label">不喜欢</span>
                      </label>
                    );
                  })}
                </div>

                <footer className="review-footer">
                  <button type="button" className="nav-button secondary" disabled={reviewPage === 0 || saveState === 'saving'} onClick={() => void moveToPage(reviewPage - 1)}>← 返回</button>
                  <span className={`save-indicator ${saveState}`} aria-live="polite">
                    {saveState === 'saving' ? '正在保存…' : saveState === 'error' ? '保存失败，请重试' : saveState === 'saved' ? '已保存' : ''}
                  </span>
                  {reviewPage < pageCount - 1 ? (
                    <button type="button" className="nav-button primary" disabled={saveState === 'saving'} onClick={() => void moveToPage(reviewPage + 1)}>下一页 →</button>
                  ) : (
                    <button type="button" className="nav-button finish" disabled={saveState === 'saving'} onClick={() => setConfirmOpen(true)}>完成筛选</button>
                  )}
                </footer>
              </>
            )}
          </section>
        ) : (
          <>

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
                <h2>
                  {(paper.links?.publication ?? paper.links?.arxiv ?? paper.links?.submission ?? paper.url)
                    ? <a href={paper.links?.publication ?? paper.links?.arxiv ?? paper.links?.submission ?? paper.url} target="_blank" rel="noreferrer">{paper.title}</a>
                    : paper.title}
                </h2>
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
                  </span>
                </div>
              </article>
            ))}
          </div>
        )}
          </>
        )}
      </main>

      {confirmOpen && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setConfirmOpen(false)}>
          <div className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title" onMouseDown={(event) => event.stopPropagation()}>
            <p className="eyebrow">FINAL CONFIRMATION</p>
            <h2 id="confirm-title">提交筛选结果？</h2>
            <p>你已勾选 <strong>{selectedIds.length}</strong> 篇不喜欢的论文。提交后名单会锁定，但论文不会立刻删除。</p>
            <div className="dialog-actions">
              <button type="button" className="nav-button secondary" onClick={() => setConfirmOpen(false)}>继续检查</button>
              <button type="button" className="nav-button finish" onClick={() => void completeReview()}>确认提交</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
