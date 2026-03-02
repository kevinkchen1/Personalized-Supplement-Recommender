import { useState } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";
import { Link } from "react-router-dom";
import { usePatientProfile } from "../profileContext";

type Message = {
  role: "user" | "assistant";
  content: string;
};

const API_BASE_URL = "http://localhost:8000";

export function ChatPage() {
  const { profile } = usePatientProfile();
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
          medications: profile.medications,
          supplements: profile.supplements,
          conditions: profile.conditions
            .split(",")
            .map((c) => c.trim())
            .filter(Boolean),
          dietary_restrictions: profile.dietary_restrictions
            .split(",")
            .map((d) => d.trim())
            .filter(Boolean),
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

  const handleKeyDown: React.KeyboardEventHandler<HTMLInputElement> = (
    event,
  ) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  };

  return (
    <div className="shell">
      <header className="nav">
        <div className="nav-left">
          <span className="nav-logo-dot" />
          <span className="nav-brand">Supplement Recommender</span>
        </div>
        <nav className="nav-links">
          <Link to="/" className="nav-link-quiet">
            Edit Profile
          </Link>
        </nav>
      </header>

      <main className="chat-layout">
        <section className="summary-card">
          <h2 className="card-title">Current Patient Profile</h2>
          <p className="card-subtitle">
            This is the information the agent is using to evaluate safety,
            deficiencies, and recommendations.
          </p>
          <div className="summary-section">
            <h3>Medications</h3>
            <p>{profile.medications || "Not provided"}</p>
          </div>
          <div className="summary-section">
            <h3>Supplements</h3>
            <p>{profile.supplements || "Not provided"}</p>
          </div>
          <div className="summary-inline">
            <div>
              <h3>Conditions</h3>
              <p>{profile.conditions || "None listed"}</p>
            </div>
            <div>
              <h3>Dietary</h3>
              <p>{profile.dietary_restrictions || "None listed"}</p>
            </div>
          </div>
        </section>

        <section className="chat-panel light">
          <h2 className="card-title">Safety & Recommendations Chat</h2>
          <p className="card-subtitle">
            Ask about supplement–medication safety, nutrient deficiencies, or
            safe options for a symptom or condition.
          </p>
          <div className="chat-window light">
            {messages.length === 0 && (
              <div className="chat-empty light">
                <p>
                  Try questions like:
                </p>
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

          <div className="chat-input-row">
            <input
              type="text"
              placeholder="Ask a safety, deficiency, or recommendation question…"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading}
            />
            <button onClick={sendMessage} disabled={isLoading}>
              {isLoading ? "Sending..." : "Send"}
            </button>
          </div>
        </section>
      </main>
    </div>
  );
}

