import { useState } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";

type Message = {
  role: "user" | "assistant";
  content: string;
};

type PatientProfile = {
  medications: string;
  supplements: string;
  conditions: string;
  dietary_restrictions: string;
};

const API_BASE_URL = "http://localhost:8000";

export function App() {
  const [profile, setProfile] = useState<PatientProfile>({
    medications: "",
    supplements: "",
    conditions: "",
    dietary_restrictions: "",
  });

  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleProfileChange = (
    field: keyof PatientProfile,
    value: string,
  ) => {
    setProfile((prev) => ({ ...prev, [field]: value }));
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
    <div className="app-container">
      <header className="app-header">
        <div>
          <h1>Personalized Supplement Safety Advisor</h1>
          <p>
            Check supplement–medication safety, deficiencies, and
            recommendations using your existing LangGraph + Neo4j backend.
          </p>
        </div>
      </header>

      <main className="app-main">
        <section className="profile-panel">
          <h2>Patient Profile</h2>
          <div className="field-group">
            <label>Current Medications</label>
            <textarea
              placeholder="e.g. Warfarin 5mg daily"
              value={profile.medications}
              onChange={(e) =>
                handleProfileChange("medications", e.target.value)
              }
            />
          </div>
          <div className="field-group">
            <label>Current Supplements</label>
            <textarea
              placeholder="e.g. Fish Oil 1000mg, Vitamin D 2000 IU"
              value={profile.supplements}
              onChange={(e) =>
                handleProfileChange("supplements", e.target.value)
              }
            />
          </div>
          <div className="field-group">
            <label>Conditions (comma-separated)</label>
            <input
              type="text"
              placeholder="e.g. hypertension, diabetes"
              value={profile.conditions}
              onChange={(e) =>
                handleProfileChange("conditions", e.target.value)
              }
            />
          </div>
          <div className="field-group">
            <label>Dietary Restrictions (comma-separated)</label>
            <input
              type="text"
              placeholder="e.g. vegan, gluten-free"
              value={profile.dietary_restrictions}
              onChange={(e) =>
                handleProfileChange("dietary_restrictions", e.target.value)
              }
            />
          </div>
        </section>

        <section className="chat-panel">
          <h2>Safety & Recommendations Chat</h2>
          <div className="chat-window">
            {messages.length === 0 && (
              <div className="chat-empty">
                <p>
                  Start by entering the patient profile on the left, then ask a
                  question like:
                </p>
                <ul>
                  <li>“Is Fish Oil safe with Warfarin?”</li>
                  <li>“Which supplements are safe for joint pain?”</li>
                  <li>
                    “Do any of my medications deplete important nutrients?”
                  </li>
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
                <div className="chat-message-content">
                  <ReactMarkdown>{m.content}</ReactMarkdown>
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="chat-message chat-message-bot">
                <div className="chat-message-role">Advisor</div>
                <div className="chat-message-content">
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

