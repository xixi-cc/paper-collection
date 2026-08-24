export default {
    async fetch(request, env) {
        const url = new URL(request.url);

        if (url.pathname === '/api/review') {
            return handleReview(request, env);
        }

        const response = await env.ASSETS.fetch(request);
        if (response.status !== 404 || request.method !== 'GET') {
            return response;
        }

        const fallbackUrl = new URL(request.url);
        fallbackUrl.pathname = '/index.html';
        return env.ASSETS.fetch(new Request(fallbackUrl, request));
    },
};

const CREATE_REVIEW_SESSIONS = `
    CREATE TABLE IF NOT EXISTS review_sessions (
        session_id TEXT PRIMARY KEY,
        selected_ids TEXT NOT NULL DEFAULT '[]',
        current_page INTEGER NOT NULL DEFAULT 0,
        total_papers INTEGER NOT NULL DEFAULT 0,
        completed INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        completed_at TEXT
    )
`;

async function handleReview(request, env) {
    if (!env.DB) {
        return json({ error: 'Review storage is unavailable.' }, 503);
    }

    await env.DB.prepare(CREATE_REVIEW_SESSIONS).run();

    if (request.method === 'GET') {
        const sessionId = new URL(request.url).searchParams.get('session');
        if (!validSessionId(sessionId)) return json({ error: 'Invalid review session.' }, 400);

        const row = await env.DB.prepare(
            'SELECT selected_ids, current_page, total_papers, completed, updated_at, completed_at FROM review_sessions WHERE session_id = ?'
        ).bind(sessionId).first();

        return json(row ? {
            selectedIds: JSON.parse(row.selected_ids),
            currentPage: row.current_page,
            totalPapers: row.total_papers,
            completed: Boolean(row.completed),
            updatedAt: row.updated_at,
            completedAt: row.completed_at,
        } : null);
    }

    if (request.method === 'POST') {
        let body;
        try {
            body = await request.json();
        } catch {
            return json({ error: 'Invalid JSON body.' }, 400);
        }

        const sessionId = body?.sessionId;
        const selectedIds = body?.selectedIds;
        const currentPage = body?.currentPage;
        const totalPapers = body?.totalPapers;
        const completed = body?.completed === true;

        if (!validSessionId(sessionId)
            || !Array.isArray(selectedIds)
            || selectedIds.length > 5000
            || selectedIds.some((id) => typeof id !== 'string' || id.length > 200)
            || !Number.isInteger(currentPage) || currentPage < 0
            || !Number.isInteger(totalPapers) || totalPapers < 0 || totalPapers > 100000) {
            return json({ error: 'Invalid review data.' }, 400);
        }

        const now = new Date().toISOString();
        const selectedJson = JSON.stringify([...new Set(selectedIds)]);
        await env.DB.prepare(`
            INSERT INTO review_sessions (
                session_id, selected_ids, current_page, total_papers, completed,
                created_at, updated_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                selected_ids = CASE WHEN review_sessions.completed = 1 THEN review_sessions.selected_ids ELSE excluded.selected_ids END,
                current_page = CASE WHEN review_sessions.completed = 1 THEN review_sessions.current_page ELSE excluded.current_page END,
                total_papers = CASE WHEN review_sessions.completed = 1 THEN review_sessions.total_papers ELSE excluded.total_papers END,
                completed = CASE WHEN review_sessions.completed = 1 THEN 1 ELSE excluded.completed END,
                updated_at = excluded.updated_at,
                completed_at = CASE
                    WHEN review_sessions.completed_at IS NOT NULL THEN review_sessions.completed_at
                    ELSE excluded.completed_at
                END
        `).bind(
            sessionId,
            selectedJson,
            currentPage,
            totalPapers,
            completed ? 1 : 0,
            now,
            now,
            completed ? now : null,
        ).run();

        return json({ ok: true, completed });
    }

    return json({ error: 'Method not allowed.' }, 405, { Allow: 'GET, POST' });
}

function validSessionId(value) {
    return typeof value === 'string' && /^[a-f0-9-]{36}$/.test(value);
}

function json(value, status = 200, headers = {}) {
    return new Response(JSON.stringify(value), {
        status,
        headers: { 'content-type': 'application/json; charset=utf-8', ...headers },
    });
}
