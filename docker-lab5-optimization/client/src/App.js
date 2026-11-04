import { useEffect, useMemo, useRef, useState } from 'react';

const categories = ['Все статьи', 'Сборка', 'Безопасность', 'Основы'];

function App() {
  const [posts, setPosts] = useState([]);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState('');
  const [category, setCategory] = useState('Все статьи');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState(null);
  const dialog = useRef(null);

  useEffect(() => {
    const controller = new AbortController();
    const request = async () => {
      try {
        const [healthResponse, postsResponse] = await Promise.all([
          fetch('/api/health', { signal: controller.signal }),
          fetch('/api/posts', { signal: controller.signal })
        ]);
        if (!healthResponse.ok || !postsResponse.ok) throw new Error('Сервер временно недоступен');
        const health = await healthResponse.json();
        const data = await postsResponse.json();
        if (health.status !== 'ok' || !Array.isArray(data)) throw new Error('Неожиданный ответ API');
        setPosts(data);
        setStatus('ready');
      } catch (err) {
        if (err.name !== 'AbortError') {
          setError(err.message);
          setStatus('error');
        }
      }
    };
    request();
    return () => controller.abort();
  }, []);

  const visiblePosts = useMemo(() => posts.filter(post => {
    const matchesCategory = category === 'Все статьи' || post.category === category;
    const matchesSearch = `${post.title} ${post.excerpt} ${post.content.join(' ')}`
      .toLocaleLowerCase('ru').includes(search.toLocaleLowerCase('ru').trim());
    return matchesCategory && matchesSearch;
  }), [posts, category, search]);

  useEffect(() => {
    if (selected && dialog.current && !dialog.current.open) dialog.current.showModal();
  }, [selected]);

  function closeArticle() {
    if (dialog.current?.open) dialog.current.close();
    setSelected(null);
  }

  return (
    <div className="site-shell">
      <header className="site-header">
        <a className="brand" href="/" aria-label="Docker Blog, главная">
          <span className="brand-mark" aria-hidden="true">D</span>
          <span>docker<span className="brand-light"> / blog</span></span>
        </a>
        <div className={`server-state ${status}`} aria-live="polite">
          <span aria-hidden="true" />
          {status === 'ready' ? 'Express API работает' : status === 'error' ? 'API недоступен' : 'Подключаем API…'}
        </div>
      </header>

      <main>
        <section className="hero" aria-labelledby="page-title">
          <div>
            <p className="eyebrow">ЛАБОРАТОРНАЯ 05 / REACT + EXPRESS</p>
            <h1 id="page-title">Меньше образ.<br /><em>Больше понимания.</em></h1>
            <p className="hero-description">Заметки о контейнерах, осмысленных сборках и привычках, которые стоит забрать в следующий проект.</p>
          </div>
          <div className="build-illustration" aria-label="Исходники проходят через стадию сборки в небольшой runtime-образ">
            <div className="terminal-bar"><span /><span /><span /><small>Dockerfile</small></div>
            <div className="terminal-body"><p><b>FROM</b> node:24 <i>AS react-build</i></p><p><b>RUN</b> npm run build</p><div className="terminal-divider" /><p><b>FROM</b> node:24-alpine <i>AS production-deps</i></p><p><b>FROM</b> alpine:3.24</p><p><b>COPY</b> --from=production-deps node …</p><p><b>COPY</b> --from=react-build static …</p><p><b>USER</b> node</p><p className="terminal-comment"># только то, что нужно</p></div>
            <span className="build-label">3 STAGES → 1 RUNTIME</span>
          </div>
        </section>

        <section className="articles" aria-labelledby="articles-title">
          <div className="section-heading"><div><p className="eyebrow">ИЗ ПРАКТИКИ</p><h2 id="articles-title">Записи в блоге</h2></div><label className="search"><span aria-hidden="true">⌕</span><input aria-label="Поиск по статьям" type="search" placeholder="Найти статью" value={search} onChange={event => setSearch(event.target.value)} /></label></div>
          <div className="filters" aria-label="Категории статей">{categories.map(item => <button key={item} className={category === item ? 'active' : ''} onClick={() => setCategory(item)} aria-pressed={category === item}>{item}</button>)}</div>
          {status === 'loading' && <p className="notice" role="status">Загружаем статьи из Express API…</p>}
          {status === 'error' && <div className="notice error" role="alert"><strong>{error}.</strong> Проверьте /api/health и логи контейнера, затем обновите страницу.</div>}
          {status === 'ready' && <div className="post-grid">{visiblePosts.map(post => <article className="post-card" key={post.id}>
            <div className={`post-art art-${post.id}`} aria-hidden="true"><span className="art-number">0{post.id}</span><span className="art-code">{post.code}</span><span className="art-caption">{post.kicker}</span></div>
            <div className="post-body"><div className="post-meta"><span>{post.category}</span><span>{post.minutes} мин чтения</span></div><h3><button onClick={() => setSelected(post)}>{post.title}</button></h3><p>{post.excerpt}</p><button className="read-link" onClick={() => setSelected(post)} aria-label={`Читать статью ${post.title}`}>Читать статью <span aria-hidden="true">↗</span></button></div>
          </article>)}</div>}
          {status === 'ready' && visiblePosts.length === 0 && <p className="notice">Статей по этому запросу пока нет. Попробуйте другое слово или категорию.</p>}
        </section>
      </main>

      <footer><p>Docker Blog <span>·</span> Учебный проект DevOps</p><p>CRA production build / Express / non-root runtime</p></footer>

      <dialog ref={dialog} onCancel={closeArticle} onClose={() => setSelected(null)} aria-labelledby="article-title">
        {selected && <div className="article-dialog"><button className="close-dialog" onClick={closeArticle} aria-label="Закрыть статью">×</button><p className="eyebrow">{selected.category} / {selected.minutes} МИН ЧТЕНИЯ</p><h2 id="article-title">{selected.title}</h2><p className="article-lead">{selected.excerpt}</p>{selected.content.map((paragraph, index) => <p key={index}>{paragraph}</p>)}<code>{selected.code}</code></div>}
      </dialog>
    </div>
  );
}

export default App;
