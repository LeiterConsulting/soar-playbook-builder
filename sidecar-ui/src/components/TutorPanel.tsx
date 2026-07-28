import { useCallback, useEffect, useState } from "react";
import { useBuilder } from "../context/BuilderProvider";

interface LessonRow {
  slug: string;
  title: string;
}

export function TutorPanel() {
  const b = useBuilder();
  const [lessons, setLessons] = useState<LessonRow[]>([]);
  const [loading, setLoading] = useState(true);

  const loadLesson = useCallback(
    async (slug: string) => {
      b.setInput(`lesson ${slug}`);
      const data = await b.apiGet({ action: "get_lesson", slug });
      if (data.content) {
        b.addMsg(`lesson ${slug}`, "user");
        b.addMsg(data.content, "bot");
      } else if (data.error) {
        b.addMsg(String(data.error), "bot");
      }
    },
    [b],
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const data = await b.apiGet({ action: "list_lessons" });
        if (!cancelled && data.lessons) {
          setLessons(data.lessons as LessonRow[]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [b]);

  return (
    <section className="app-section tutor-panel">
      <div className="app-section-header">Explain — lessons & quizzes</div>
      <div className="app-section-body">
        <p className="tutor-intro">
          Offline tutor lane — no LLM required. Ask in chat:{" "}
          <code>lesson 01-hello-playbook</code>, <code>quiz datapaths</code>, or{" "}
          <code>explain artifact:*.cef.sourceAddress</code>.
        </p>
        {loading && <p className="coach-status">Loading curriculum…</p>}
        {!loading && (
          <ul className="tutor-lesson-list">
            {lessons.map((row) => (
              <li key={row.slug}>
                <button type="button" className="btn btn-ghost btn-sm tutor-lesson-btn" onClick={() => void loadLesson(row.slug)}>
                  {row.title}
                </button>
                <span className="tutor-lesson-slug">{row.slug}</span>
              </li>
            ))}
          </ul>
        )}
        <div className="tutor-quick-prompts">
          <span className="tutor-quick-label">Quick prompts:</span>
          {["quiz datapaths", "lesson curriculum", "explain artifact:*.cef.sourceAddress"].map((p) => (
            <button
              key={p}
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => void b.sendMessage(p, { lane: "tutor" })}
            >
              {p}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
