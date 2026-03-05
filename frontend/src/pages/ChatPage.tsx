import { useState } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";
import { usePatientProfile } from "../profileContext";
import { MultiSelect } from "../components/MultiSelect";
import {
  COMMON_CONDITIONS,
  COMMON_DIETARY_RESTRICTIONS,
  COMMON_MEDICATIONS,
  COMMON_SUPPLEMENTS,
} from "../profileOptions";

type Message = {
  role: "user" | "assistant";
  content: string;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

// Helpful during deployment: see what URL got baked into the bundle.
// In production this will log once in the browser console.
// eslint-disable-next-line no-console
console.log(
  "[ChatPage] API_BASE_URL =",
  API_BASE_URL,
  "VITE_API_BASE_URL =",
  import.meta.env.VITE_API_BASE_URL,
);

export function ChatPage() {
  const { profile, setProfile } = usePatientProfile();
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  const setProfileList = (field: keyof typeof profile, next: string[]) => {
    setProfile((prev) => ({ ...prev, [field]: next }));
  };

  const sendMessage = async () => {
    if (!question.trim()) return;

    setError(null);
    const userMessage: Message = { role: "user", content: question.trim() };
    setMessages((prev) => [...prev, userMessage]);
    setIsLoading(true);

    try {
      const response = await axios.post(`${API_BASE_URL}/chat`, {
        user_question: question.trim(),
        patient_profile: {
          medications: profile.medications.join(", "),
          supplements: profile.supplements.join(", "),
          conditions: profile.conditions,
          dietary_restrictions: profile.dietary_restrictions,
        },
        session_id: "demo-session",
      });

      const botText =
        response.data.final_answer ??
        "The system did not return a final answer. Please try again.";

      const botMessage: Message = {
        role: "assistant",
        content: botText,
      };
      setMessages((prev) => [...prev, botMessage]);
      setQuestion("");
    } catch (err: any) {
      console.error(err);
      setError(
        err?.response?.data?.detail ??
          "Something went wrong talking to the backend.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown: React.KeyboardEventHandler<
    HTMLInputElement | HTMLTextAreaElement
  > = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  };

  return (
    <div className="shell shell--chat">
      <header className="nav nav--chat">
        <div className="nav-left">
          <span className="nav-brand">Supplement Recommender</span>
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
            <svg
              viewBox="0 0 24 24"
              width="32"
              height="32"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.7"
            >
              <rect
                x="4"
                y="4"
                width="16"
                height="16"
                rx="2.5"
                ry="2.5"
              />
              <path d="M8 9h5" />
              <path d="M8 13h5" />
              <path d="M8 17h3.2" />
              <path d="m15 9 1.8 1.8 3.2-3.2" />
            </svg>
          </span>
          <span className="profile-hero-label">Patient profile</span>
        </button>
      </div>

      <main className="chat-layout">
        <section className="chat-panel chat-panel--full">
          <div className="chat-window chat-window--full light">
            {messages.length === 0 && (
              <div className="chat-empty chat-empty--centered light">
                <p className="chat-empty-title">Supplement Recommender</p>
                <p className="chat-empty-subtitle">
                  Ask about supplement–medication safety, nutrient deficiencies, or
                  safe options for a symptom or condition.
                </p>
                <p className="chat-empty-hint">Try questions like:</p>
                <ul>
                  <li>“Is Fish Oil safe with Warfarin?”</li>
                  <li>“Which supplements are safest for heart health?”</li>
                  <li>“Are any nutrients depleted by my medications?”</li>
                </ul>
              </div>
            )}
            {messages.map((m, idx) => (
              <div
                key={idx}
                className={`chat-message ${
                  m.role === "user" ? "chat-message-user" : "chat-message-bot"
                }`}
              >
                <div className="chat-message-role">
                  {m.role === "user" ? "You" : "Advisor"}
                </div>
                <div className="chat-message-content light">
                  <ReactMarkdown>{m.content}</ReactMarkdown>
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="chat-message chat-message-bot">
                <div className="chat-message-role">Advisor</div>
                <div className="chat-message-content light">
                  Thinking through graph evidence…
                </div>
              </div>
            )}
          </div>

          {error && <div className="error-banner">{error}</div>}

          <div className="chat-input-area">
            <div className="chat-input-wrapper">
              <textarea
                className="chat-input"
                placeholder="Ask a safety, deficiency, or recommendation question…"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
                rows={1}
              />
              <button
                className="chat-send-btn"
                onClick={sendMessage}
                disabled={isLoading}
              >
                {isLoading ? "Sending..." : "Send"}
              </button>
            </div>
          </div>
        </section>
      </main>

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
                ×
              </button>
            </div>
            <div className="side-panel-body">
              <p className="card-subtitle">
                Update the medications, supplements, and health context that the
                agent will use when answering your questions.
              </p>

              <MultiSelect
                label="Current Medications"
                placeholder="Search meds or add custom…"
                options={COMMON_MEDICATIONS}
                selected={profile.medications}
                onChange={(next) => setProfileList("medications", next)}
              />

              <MultiSelect
                label="Current Supplements"
                placeholder="Search supplements or add custom…"
                options={COMMON_SUPPLEMENTS}
                selected={profile.supplements}
                onChange={(next) => setProfileList("supplements", next)}
              />

              <MultiSelect
                label="Conditions"
                placeholder="Search conditions or add custom…"
                options={COMMON_CONDITIONS}
                selected={profile.conditions}
                onChange={(next) => setProfileList("conditions", next)}
              />

              <MultiSelect
                label="Dietary Restrictions"
                placeholder="Search diet tags or add custom…"
                options={COMMON_DIETARY_RESTRICTIONS}
                selected={profile.dietary_restrictions}
                onChange={(next) =>
                  setProfileList("dietary_restrictions", next)
                }
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

