import { useState } from "react";
import ReactMarkdown from "react-markdown";
import { usePatientProfile } from "../profileContext";
import { MultiSelect } from "../components/MultiSelect";
import {
  COMMON_CONDITIONS,
  COMMON_DIETARY_RESTRICTIONS,
  COMMON_MEDICATIONS,
  COMMON_SUPPLEMENTS,
} from "../profileOptions";

type QAEntry = {
  question: string;
  answer: string;
  timestamp: Date;
  provenance?: ProvenanceData;
};

type ThinkingStep = {
  node: string;
  description: string;
  status: "active" | "completed";
  decision?: string;
};

type QueryRecord = {
  query: string;
  parameters: Record<string, unknown>;
  result_count: number;
  node?: string;
};

type ProvenanceData = {
  evidence_chain: string[];
  workflow_steps: string[];
  all_queries: QueryRecord[];
  safety_results: Record<string, unknown> | null;
  deficiency_results: Record<string, unknown> | null;
  recommendation_results: Record<string, unknown> | null;
  iterations: number;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

console.log(
  "[ChatPage] API_BASE_URL =",
  API_BASE_URL,
  "VITE_API_BASE_URL =",
  import.meta.env.VITE_API_BASE_URL,
);

const NODE_ICONS: Record<string, string> = {
  entity_extractor: "\u{1F50D}",
  entity_normalizer: "\u{1F517}",
  supervisor: "\u{1F9E0}",
  safety_check: "\u{26A0}\u{FE0F}",
  deficiency_check: "\u{1F48A}",
  recommendation: "\u{2728}",
  synthesis: "\u{1F4DD}",
};

const NODE_LABELS: Record<string, string> = {
  entity_extractor: "Entity Extraction",
  entity_normalizer: "Entity Normalization",
  supervisor: "Supervisor",
  safety_check: "Safety Check",
  deficiency_check: "Deficiency Check",
  recommendation: "Recommendation",
  synthesis: "Synthesis",
};

export function ChatPage() {
  const { profile, setProfile } = usePatientProfile();
  const [question, setQuestion] = useState("");
  const [currentAnswer, setCurrentAnswer] = useState<string | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<string | null>(null);
  const [history, setHistory] = useState<QAEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const [selectedHistoryItem, setSelectedHistoryItem] = useState<QAEntry | null>(null);
  const [thinkingSteps, setThinkingSteps] = useState<ThinkingStep[]>([]);
  const [provenance, setProvenance] = useState<ProvenanceData | null>(null);
  const [isProvenanceOpen, setIsProvenanceOpen] = useState(false);
  const [expandedQueries, setExpandedQueries] = useState<Set<number>>(new Set());

  const setProfileList = (field: keyof typeof profile, next: string[]) => {
    setProfile((prev) => ({ ...prev, [field]: next }));
  };

  const toggleQueryExpand = (idx: number) => {
    setExpandedQueries((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const submitQuestion = async () => {
    if (!question.trim()) return;

    setError(null);
    setCurrentQuestion(question.trim());
    setCurrentAnswer(null);
    setSelectedHistoryItem(null);
    setIsLoading(true);
    setProvenance(null);
    setThinkingSteps([
      {
        node: "starting",
        description: "Starting workflow...",
        status: "active",
      },
    ]);

    const submittedQuestion = question.trim();
    setQuestion("");

    try {
      const response = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_question: submittedQuestion,
          patient_profile: {
            medications: profile.medications.join(", "),
            supplements: profile.supplements.join(", "),
            conditions: profile.conditions,
            dietary_restrictions: profile.dietary_restrictions,
          },
          session_id: "demo-session",
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const jsonStr = line.slice(6);
          if (!jsonStr.trim()) continue;

          try {
            const data = JSON.parse(jsonStr);

            if (data.type === "step") {
              setThinkingSteps((prev) => {
                const updated = prev.map((s) => ({
                  ...s,
                  status: "completed" as const,
                }));
                return [
                  ...updated,
                  {
                    node: data.node,
                    description: data.description,
                    status: "active" as const,
                    decision: data.decision,
                  },
                ];
              });
            } else if (data.type === "result") {
              setThinkingSteps((prev) =>
                prev.map((s) => ({ ...s, status: "completed" as const }))
              );

              const answerText =
                data.final_answer ??
                "The system did not return a final answer. Please try again.";

              const prov: ProvenanceData = {
                evidence_chain: data.evidence_chain ?? [],
                workflow_steps: data.workflow_steps ?? [],
                all_queries: data.all_queries ?? [],
                safety_results: data.safety_results,
                deficiency_results: data.deficiency_results,
                recommendation_results: data.recommendation_results,
                iterations: data.iterations ?? 0,
              };

              setCurrentAnswer(answerText);
              setProvenance(prov);
              setHistory((prev) => [
                {
                  question: submittedQuestion,
                  answer: answerText,
                  timestamp: new Date(),
                  provenance: prov,
                },
                ...prev,
              ]);
            } else if (data.type === "error") {
              setError(data.message);
            }
          } catch {
            console.warn("Failed to parse SSE data:", jsonStr);
          }
        }
      }
    } catch (err: any) {
      console.error(err);
      setError(err?.message ?? "Something went wrong talking to the backend.");
      setCurrentQuestion(null);
    } finally {
      setIsLoading(false);
    }
  };

  const resetToNewQuestion = () => {
    setCurrentQuestion(null);
    setCurrentAnswer(null);
    setError(null);
    setSelectedHistoryItem(null);
    setThinkingSteps([]);
    setProvenance(null);
  };

  const viewHistoryItem = (item: QAEntry) => {
    setSelectedHistoryItem(item);
    setCurrentQuestion(null);
    setCurrentAnswer(null);
    setThinkingSteps([]);
    setProvenance(item.provenance ?? null);
    setIsHistoryOpen(false);
  };

  const openProvenance = () => {
    setExpandedQueries(new Set());
    setIsProvenanceOpen(true);
  };

  const handleKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitQuestion();
    }
  };

  const formatTime = (date: Date) =>
    date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  const activeProvenance = selectedHistoryItem?.provenance ?? provenance;
  const showingResult = currentAnswer || selectedHistoryItem;

  const renderSpecialistSummary = (
    label: string,
    results: Record<string, unknown> | null | undefined,
  ) => {
    if (!results) return null;
    const status = String(results.status ?? "");
    const summary = String(results.summary ?? "");
    if (!summary) return null;

    const interactions = results.interactions as Array<Record<string, string>> | undefined;
    const allAtRisk = results.all_at_risk as string[] | undefined;
    const recommendations = results.recommendations as Array<Record<string, string>> | undefined;

    return (
      <div className="prov-specialist">
        <div className="prov-specialist-header">
          <span className="prov-specialist-label">{label}</span>
          <span
            className={`prov-specialist-status prov-status--${status === "found" ? "found" : "clear"}`}
          >
            {status === "found" ? "Findings" : "No findings"}
          </span>
        </div>
        <p className="prov-specialist-summary">{summary}</p>
        {status === "found" && interactions && interactions.length > 0 && (
          <ul className="prov-findings">
            {interactions.map((ix, i) => (
              <li key={i} className="prov-finding">
                <strong>
                  {ix.supplement} / {ix.target}
                </strong>{" "}
                ({ix.pathway?.replace(/_/g, " ")}) &mdash;{" "}
                {ix.description || ix.clinical_reasoning}
              </li>
            ))}
          </ul>
        )}
        {status === "found" && allAtRisk && allAtRisk.length > 0 && (
          <p className="prov-finding-detail">
            Nutrients at risk: {allAtRisk.join(", ")}
          </p>
        )}
        {status === "found" && recommendations && recommendations.length > 0 && (
          <ul className="prov-findings">
            {recommendations.map((rec, i) => (
              <li key={i} className="prov-finding">
                <strong>{rec.supplement_name}</strong> (safety:{" "}
                {rec.safety_rating}) &mdash; treats {rec.symptom_treated}
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  };

  return (
    <div className="shell shell--qa">
      <header className="nav nav--chat">
        <div className="nav-left">
          <span className="nav-brand">Supplement Recommender</span>
        </div>
        <div className="nav-right">
          {history.length > 0 && (
            <button
              type="button"
              className="nav-history-btn"
              onClick={() => setIsHistoryOpen(true)}
              aria-label="View history"
            >
              <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <polyline points="12 6 12 12 16 14" />
              </svg>
              <span>History ({history.length})</span>
            </button>
          )}
        </div>
      </header>

      <div className="profile-hero-bar">
        <button
          type="button"
          className="profile-hero-btn"
          onClick={() => setIsProfileOpen(true)}
          aria-label="Set patient profile"
        >
          <span className="profile-hero-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="currentColor" strokeWidth="1.7">
              <rect x="4" y="4" width="16" height="16" rx="2.5" ry="2.5" />
              <path d="M8 9h5" />
              <path d="M8 13h5" />
              <path d="M8 17h3.2" />
              <path d="m15 9 1.8 1.8 3.2-3.2" />
            </svg>
          </span>
          <span className="profile-hero-label">Patient profile</span>
        </button>
      </div>

      <main className="qa-layout">
        {!showingResult && !isLoading ? (
          <div className="qa-input-section">
            <div className="qa-welcome">
              <h1 className="qa-title">Supplement Recommender</h1>
              <p className="qa-subtitle">
                Ask about supplement-medication safety, nutrient deficiencies, or
                safe options for a symptom or condition.
              </p>
              <p className="qa-hint">Try questions like:</p>
              <ul className="qa-examples">
                <li>&quot;Is Fish Oil safe with Warfarin?&quot;</li>
                <li>&quot;Which supplements are safest for heart health?&quot;</li>
                <li>&quot;Are any nutrients depleted by my medications?&quot;</li>
              </ul>
            </div>

            <div className="qa-input-area">
              <div className="qa-input-wrapper">
                <textarea
                  className="qa-input"
                  placeholder="Type your question here..."
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={3}
                  autoFocus
                />
                <button
                  className="qa-submit-btn"
                  onClick={submitQuestion}
                  disabled={!question.trim()}
                >
                  Get Answer
                </button>
              </div>
            </div>
          </div>
        ) : isLoading ? (
          <div className="qa-thinking-section">
            <div className="qa-thinking-header">
              <p className="qa-thinking-question">&quot;{currentQuestion}&quot;</p>
            </div>
            <div className="qa-thinking-steps">
              <h3 className="qa-thinking-title">Analyzing your question...</h3>
              <ul className="thinking-list">
                {thinkingSteps.map((step, idx) => (
                  <li
                    key={idx}
                    className={`thinking-item ${step.status === "active" ? "thinking-item--active" : "thinking-item--completed"}`}
                  >
                    <span className="thinking-icon">
                      {step.status === "active" ? (
                        <span className="thinking-spinner" />
                      ) : (
                        <span className="thinking-check">{"\u2713"}</span>
                      )}
                    </span>
                    <span className="thinking-emoji">{NODE_ICONS[step.node] || "\u2699\uFE0F"}</span>
                    <span className="thinking-text">{step.description}</span>
                    {step.decision && (
                      <span className="thinking-decision">
                        {"\u2192"} {step.decision.replace(/_/g, " ")}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        ) : (
          <div className="qa-result-section">
            <div className="qa-result-card">
              <div className="qa-question-display">
                <span className="qa-label">Question</span>
                <p className="qa-question-text">
                  {selectedHistoryItem ? selectedHistoryItem.question : currentQuestion}
                </p>
              </div>
              <div className="qa-answer-display">
                <span className="qa-label">Answer</span>
                <div className="qa-answer-content">
                  <ReactMarkdown>
                    {selectedHistoryItem ? selectedHistoryItem.answer : currentAnswer!}
                  </ReactMarkdown>
                </div>
              </div>
              {activeProvenance && (
                <div className="qa-provenance-bar">
                  <button className="qa-provenance-btn" onClick={openProvenance}>
                    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10" />
                      <line x1="12" y1="16" x2="12" y2="12" />
                      <line x1="12" y1="8" x2="12.01" y2="8" />
                    </svg>
                    How this answer was generated
                  </button>
                </div>
              )}
            </div>

            {error && <div className="error-banner">{error}</div>}

            <button className="qa-new-question-btn" onClick={resetToNewQuestion}>
              Ask Another Question
            </button>
          </div>
        )}
      </main>

      {/* Provenance Modal */}
      {isProvenanceOpen && activeProvenance && (
        <>
          <div
            className="prov-backdrop"
            onClick={() => setIsProvenanceOpen(false)}
            aria-hidden="true"
          />
          <div className="prov-modal">
            <div className="prov-modal-header">
              <h2 className="prov-modal-title">How this answer was generated</h2>
              <button
                type="button"
                className="prov-modal-close"
                onClick={() => setIsProvenanceOpen(false)}
                aria-label="Close"
              >
                {"\u00D7"}
              </button>
            </div>
            <div className="prov-modal-body">
              {/* Workflow Steps */}
              <section className="prov-section">
                <h3 className="prov-section-title">Workflow Pipeline</h3>
                <div className="prov-pipeline">
                  {activeProvenance.workflow_steps.map((step, idx) => (
                    <span key={idx} className="prov-pipeline-step">
                      <span className="prov-pipeline-icon">
                        {NODE_ICONS[step] || "\u2699\uFE0F"}
                      </span>
                      <span className="prov-pipeline-label">
                        {NODE_LABELS[step] || step}
                      </span>
                      {idx < activeProvenance.workflow_steps.length - 1 && (
                        <span className="prov-pipeline-arrow">{"\u2192"}</span>
                      )}
                    </span>
                  ))}
                </div>
                <p className="prov-iterations">
                  Supervisor iterations: {activeProvenance.iterations}
                </p>
              </section>

              {/* Evidence Chain */}
              <section className="prov-section">
                <h3 className="prov-section-title">Evidence Chain</h3>
                <ol className="prov-evidence-list">
                  {activeProvenance.evidence_chain.map((entry, idx) => (
                    <li key={idx} className="prov-evidence-item">
                      {entry}
                    </li>
                  ))}
                </ol>
              </section>

              {/* Specialist Results */}
              {(activeProvenance.safety_results ||
                activeProvenance.deficiency_results ||
                activeProvenance.recommendation_results) && (
                <section className="prov-section">
                  <h3 className="prov-section-title">Specialist Results</h3>
                  {renderSpecialistSummary("Safety Check", activeProvenance.safety_results)}
                  {renderSpecialistSummary("Deficiency Check", activeProvenance.deficiency_results)}
                  {renderSpecialistSummary("Recommendations", activeProvenance.recommendation_results)}
                </section>
              )}

              {/* Cypher Queries */}
              {activeProvenance.all_queries.length > 0 && (
                <section className="prov-section">
                  <h3 className="prov-section-title">
                    Knowledge Graph Queries ({activeProvenance.all_queries.length})
                  </h3>
                  <div className="prov-queries">
                    {activeProvenance.all_queries.map((q, idx) => (
                      <div key={idx} className="prov-query-card">
                        <button
                          className="prov-query-header"
                          onClick={() => toggleQueryExpand(idx)}
                        >
                          <span className="prov-query-node">
                            {NODE_LABELS[q.node ?? ""] || q.node}
                          </span>
                          <span className="prov-query-count">
                            {q.result_count} record{q.result_count !== 1 ? "s" : ""}
                          </span>
                          <span className="prov-query-toggle">
                            {expandedQueries.has(idx) ? "\u25B2" : "\u25BC"}
                          </span>
                        </button>
                        {expandedQueries.has(idx) && (
                          <div className="prov-query-body">
                            <pre className="prov-query-cypher">{q.query}</pre>
                            {q.parameters &&
                              Object.keys(q.parameters).length > 0 && (
                                <div className="prov-query-params">
                                  <span className="prov-query-params-label">
                                    Parameters:
                                  </span>
                                  <pre className="prov-query-params-json">
                                    {JSON.stringify(q.parameters, null, 2)}
                                  </pre>
                                </div>
                              )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </div>
          </div>
        </>
      )}

      {/* History Panel */}
      {isHistoryOpen && (
        <>
          <div
            className="side-panel-backdrop"
            onClick={() => setIsHistoryOpen(false)}
            aria-hidden="true"
          />
          <aside className="side-panel side-panel--right">
            <div className="side-panel-header">
              <h2 className="card-title">Question History</h2>
              <button
                type="button"
                className="side-panel-close"
                onClick={() => setIsHistoryOpen(false)}
                aria-label="Close history"
              >
                {"\u00D7"}
              </button>
            </div>
            <div className="side-panel-body">
              {history.length === 0 ? (
                <p className="history-empty">No questions asked yet.</p>
              ) : (
                <ul className="history-list">
                  {history.map((item, idx) => (
                    <li key={idx} className="history-item">
                      <button
                        className="history-item-btn"
                        onClick={() => viewHistoryItem(item)}
                      >
                        <span className="history-item-question">{item.question}</span>
                        <span className="history-item-time">
                          {formatTime(item.timestamp)}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </aside>
        </>
      )}

      {/* Profile Panel */}
      {isProfileOpen && (
        <>
          <div
            className="side-panel-backdrop"
            onClick={() => setIsProfileOpen(false)}
            aria-hidden="true"
          />
          <aside className="side-panel">
            <div className="side-panel-header">
              <h2 className="card-title">Patient Profile</h2>
              <button
                type="button"
                className="side-panel-close"
                onClick={() => setIsProfileOpen(false)}
                aria-label="Close profile"
              >
                {"\u00D7"}
              </button>
            </div>
            <div className="side-panel-body">
              <p className="card-subtitle">
                Update the medications, supplements, and health context that the
                agent will use when answering your questions.
              </p>
              <MultiSelect
                label="Current Medications"
                placeholder="Search meds or add custom..."
                options={COMMON_MEDICATIONS}
                selected={profile.medications}
                onChange={(next) => setProfileList("medications", next)}
              />
              <MultiSelect
                label="Current Supplements"
                placeholder="Search supplements or add custom..."
                options={COMMON_SUPPLEMENTS}
                selected={profile.supplements}
                onChange={(next) => setProfileList("supplements", next)}
              />
              <MultiSelect
                label="Conditions"
                placeholder="Search conditions or add custom..."
                options={COMMON_CONDITIONS}
                selected={profile.conditions}
                onChange={(next) => setProfileList("conditions", next)}
              />
              <MultiSelect
                label="Dietary Restrictions"
                placeholder="Search diet tags or add custom..."
                options={COMMON_DIETARY_RESTRICTIONS}
                selected={profile.dietary_restrictions}
                onChange={(next) => setProfileList("dietary_restrictions", next)}
              />
              <button
                type="button"
                className="primary-cta"
                onClick={() => setIsProfileOpen(false)}
              >
                Save and close
              </button>
            </div>
          </aside>
        </>
      )}
    </div>
  );
}
