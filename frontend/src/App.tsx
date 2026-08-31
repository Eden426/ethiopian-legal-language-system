import { FormEvent, useState } from "react";

import {
  Citation,
  Language,
  mockAnswer,
  mockSearch,
  mockTranslate,
} from "./api/mockApi";

type Workspace = "translate" | "search" | "ask";

const navigation: Array<{ id: Workspace; label: string; description: string }> = [
  { id: "translate", label: "Translate", description: "Amharic to English" },
  { id: "search", label: "Search", description: "Bilingual evidence" },
  { id: "ask", label: "Ask", description: "Cited answers" },
];

function BrandMark() {
  return (
    <span
      aria-hidden="true"
      className="grid size-11 place-items-center rounded-full border border-[#f5e6cf]/40 bg-[#9b6c2a] text-lg font-black text-white shadow-sm"
    >
      ፍ
    </span>
  );
}

function Notice({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex gap-3 rounded-xl border border-[#9b6c2a]/30 bg-[#fffaf1] px-4 py-3 text-sm leading-6 text-[#41231B]">
      <span aria-hidden="true" className="font-bold text-[#9b6c2a]">
        i
      </span>
      <p>{children}</p>
    </div>
  );
}

function CitationList({ citations }: { citations: Citation[] }) {
  return (
    <ol className="mt-5 space-y-3" aria-label="Supporting citations">
      {citations.map((citation) => (
        <li className="rounded-xl border border-[#9b6c2a]/25 bg-white p-4" key={citation.passageId}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold text-[#41231B]">{citation.label}</p>
            <code className="rounded bg-[#f5e6cf] px-2 py-1 text-xs text-[#41231B]">
              {citation.passageId}
            </code>
          </div>
          <p className="mt-2 text-sm leading-6 text-[#60453d]">{citation.excerpt}</p>
        </li>
      ))}
    </ol>
  );
}

function TranslatePanel() {
  const [text, setText] = useState("");
  const [translation, setTranslation] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      setTranslation(await mockTranslate(text));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Translation failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section aria-labelledby="translate-title">
      <div className="mb-7">
        <p className="text-sm font-bold uppercase tracking-[0.18em] text-[#9b6c2a]">Workspace 01</p>
        <h2 id="translate-title" className="mt-2 text-3xl font-bold tracking-tight text-[#41231B]">
          Amharic to English
        </h2>
        <p className="mt-2 max-w-2xl text-[#6d524a]">
          Translate Ethiopian legal text with the selected model when the inference service is connected.
        </p>
      </div>
      <form onSubmit={submit} className="grid gap-5 lg:grid-cols-2">
        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-[#41231B]">Amharic source text</span>
          <textarea
            className="min-h-64 w-full resize-y rounded-2xl border border-[#9b6c2a]/35 bg-white p-5 text-lg leading-8 text-[#41231B] outline-none transition focus:border-[#9b6c2a] focus:ring-4 focus:ring-[#9b6c2a]/15"
            dir="auto"
            maxLength={5000}
            onChange={(event) => setText(event.target.value)}
            placeholder="የአማርኛ ሕጋዊ ጽሑፍ እዚህ ያስገቡ…"
            value={text}
          />
          <span className="mt-1 block text-right text-xs text-[#80675f]">{text.length} / 5,000</span>
        </label>
        <div>
          <p className="mb-2 text-sm font-semibold text-[#41231B]">English translation</p>
          <div
            aria-live="polite"
            className="min-h-64 rounded-2xl border border-[#9b6c2a]/25 bg-[#fffaf1] p-5 text-lg leading-8 text-[#41231B]"
          >
            {loading ? "Preparing mock translation…" : translation || "Your generated translation will appear here."}
          </div>
        </div>
        <div className="lg:col-span-2 flex flex-wrap items-center justify-between gap-4">
          <p aria-live="assertive" className="text-sm font-medium text-red-800">{error}</p>
          <button
            className="rounded-xl bg-[#41231B] px-6 py-3 font-semibold text-[#f5e6cf] shadow-sm transition hover:bg-[#583126] focus:outline-none focus:ring-4 focus:ring-[#9b6c2a]/30 disabled:cursor-not-allowed disabled:opacity-60"
            disabled={loading}
            type="submit"
          >
            {loading ? "Translating…" : "Translate text"}
          </button>
        </div>
      </form>
    </section>
  );
}

function SearchPanel() {
  const [query, setQuery] = useState("");
  const [language, setLanguage] = useState<Language>("amh_Ethi");
  const [results, setResults] = useState<Citation[]>([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    setLoading(true);
    try {
      setResults(await mockSearch(query, language));
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "Search failed.");
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section aria-labelledby="search-title">
      <p className="text-sm font-bold uppercase tracking-[0.18em] text-[#9b6c2a]">Workspace 02</p>
      <h2 id="search-title" className="mt-2 text-3xl font-bold tracking-tight text-[#41231B]">
        Bilingual evidence search
      </h2>
      <p className="mt-2 text-[#6d524a]">Search approved paired passages in either language.</p>
      <form className="mt-7 flex flex-col gap-3 md:flex-row" onSubmit={submit}>
        <label className="sr-only" htmlFor="search-query">Search legal passages</label>
        <input
          id="search-query"
          className="min-w-0 flex-1 rounded-xl border border-[#9b6c2a]/35 bg-white px-4 py-3 text-[#41231B] outline-none focus:border-[#9b6c2a] focus:ring-4 focus:ring-[#9b6c2a]/15"
          dir="auto"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Search terms, article number, or phrase…"
          value={query}
        />
        <label className="sr-only" htmlFor="search-language">Query language</label>
        <select
          id="search-language"
          className="rounded-xl border border-[#9b6c2a]/35 bg-white px-4 py-3 text-[#41231B] outline-none"
          onChange={(event) => setLanguage(event.target.value as Language)}
          value={language}
        >
          <option value="amh_Ethi">Amharic</option>
          <option value="eng_Latn">English</option>
        </select>
        <button className="rounded-xl bg-[#41231B] px-6 py-3 font-semibold text-[#f5e6cf] hover:bg-[#583126] disabled:opacity-60" disabled={loading} type="submit">
          {loading ? "Searching…" : "Search evidence"}
        </button>
      </form>
      <p aria-live="assertive" className="mt-3 text-sm font-medium text-red-800">{message}</p>
      {results.length > 0 && (
        <div aria-live="polite" className="mt-8">
          <div className="flex items-end justify-between border-b border-[#9b6c2a]/25 pb-3">
            <h3 className="text-lg font-bold text-[#41231B]">Mock results</h3>
            <span className="text-sm text-[#80675f]">{results.length} passages</span>
          </div>
          <CitationList citations={results} />
        </div>
      )}
    </section>
  );
}

function AskPanel() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [citations, setCitations] = useState<Citation[]>([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    setLoading(true);
    try {
      const response = await mockAnswer(question);
      setAnswer(response.answer);
      setCitations(response.citations);
    } catch (caught) {
      setMessage(caught instanceof Error ? caught.message : "The question could not be answered.");
      setAnswer("");
      setCitations([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section aria-labelledby="ask-title">
      <p className="text-sm font-bold uppercase tracking-[0.18em] text-[#9b6c2a]">Workspace 03</p>
      <h2 id="ask-title" className="mt-2 text-3xl font-bold tracking-tight text-[#41231B]">
        Ask with evidence
      </h2>
      <p className="mt-2 text-[#6d524a]">Answers must cite indexed passages or clearly abstain.</p>
      <form className="mt-7" onSubmit={submit}>
        <label className="mb-2 block text-sm font-semibold text-[#41231B]" htmlFor="legal-question">Your question</label>
        <textarea
          id="legal-question"
          className="min-h-32 w-full rounded-2xl border border-[#9b6c2a]/35 bg-white p-4 leading-7 text-[#41231B] outline-none focus:border-[#9b6c2a] focus:ring-4 focus:ring-[#9b6c2a]/15"
          dir="auto"
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="Ask in Amharic or English…"
          value={question}
        />
        <div className="mt-3 flex flex-wrap items-center justify-between gap-4">
          <p aria-live="assertive" className="text-sm font-medium text-red-800">{message}</p>
          <button className="rounded-xl bg-[#41231B] px-6 py-3 font-semibold text-[#f5e6cf] hover:bg-[#583126] disabled:opacity-60" disabled={loading} type="submit">
            {loading ? "Checking evidence…" : "Ask question"}
          </button>
        </div>
      </form>
      {answer && (
        <article aria-live="polite" className="mt-8 rounded-2xl border-l-4 border-[#9b6c2a] bg-[#fffaf1] p-6">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-[#9b6c2a]">Mock cited answer</p>
          <p className="mt-3 text-lg leading-8 text-[#41231B]">{answer}</p>
          <CitationList citations={citations} />
        </article>
      )}
    </section>
  );
}

export default function App() {
  const [workspace, setWorkspace] = useState<Workspace>("translate");

  return (
    <div className="min-h-screen bg-[#f5e6cf] text-[#41231B]">
      <header className="bg-[#41231B] text-[#f5e6cf] shadow-lg">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-6 px-5 py-4 lg:px-8">
          <div className="flex items-center gap-3">
            <BrandMark />
            <div>
              <p className="font-bold leading-tight">Ethiopian Legal</p>
              <p className="text-xs tracking-wide text-[#f5e6cf]/70">Language System · MVP</p>
            </div>
          </div>
          <div className="hidden items-center gap-2 rounded-full border border-[#f5e6cf]/20 px-3 py-1.5 text-xs sm:flex">
            <span className="size-2 rounded-full bg-[#d2a75e]" aria-hidden="true" />
            Mock services active
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 lg:grid-cols-[250px_1fr] lg:px-8 lg:py-10">
        <aside className="rounded-2xl bg-[#41231B] p-3 text-[#f5e6cf] shadow-xl lg:min-h-[680px]">
          <p className="px-3 pb-3 pt-2 text-xs font-bold uppercase tracking-[0.18em] text-[#d8b77d]">Tools</p>
          <nav aria-label="Primary tools" className="grid gap-2 sm:grid-cols-3 lg:grid-cols-1">
            {navigation.map((item, index) => {
              const active = workspace === item.id;
              return (
                <button
                  aria-current={active ? "page" : undefined}
                  className={`rounded-xl px-4 py-3 text-left transition focus:outline-none focus:ring-2 focus:ring-[#d8b77d] ${
                    active ? "bg-[#9b6c2a] text-white shadow" : "hover:bg-white/10"
                  }`}
                  key={item.id}
                  onClick={() => setWorkspace(item.id)}
                  type="button"
                >
                  <span className="mr-3 text-xs opacity-70">0{index + 1}</span>
                  <span className="font-semibold">{item.label}</span>
                  <span className="mt-1 block pl-7 text-xs opacity-70">{item.description}</span>
                </button>
              );
            })}
          </nav>
          <div className="mt-5 border-t border-white/15 px-3 pt-5 text-xs leading-5 text-[#f5e6cf]/70">
            Corpus Builder follows after the MT and RAG foundation.
          </div>
        </aside>

        <main className="min-w-0 rounded-2xl border border-[#9b6c2a]/20 bg-[#fffdf8] p-5 shadow-xl sm:p-8 lg:p-10">
          <Notice>
            This interface currently uses fabricated mock responses. Generated output is non-official and is not legal advice.
          </Notice>
          <div className="mt-8">
            {workspace === "translate" && <TranslatePanel />}
            {workspace === "search" && <SearchPanel />}
            {workspace === "ask" && <AskPanel />}
          </div>
        </main>
      </div>

      <footer className="px-5 pb-8 text-center text-xs text-[#6d524a]">
        Built for reviewed, traceable Amharic-English legal-language workflows.
      </footer>
    </div>
  );
}
