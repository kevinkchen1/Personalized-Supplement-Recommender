import { useNavigate } from "react-router-dom";
import { usePatientProfile } from "../profileContext";

export function ProfilePage() {
  const { profile, setProfile } = usePatientProfile();
  const navigate = useNavigate();

  const handleChange = (field: keyof typeof profile, value: string) => {
    setProfile((prev) => ({ ...prev, [field]: value }));
  };

  const goToChat = () => {
    navigate("/chat");
  };

  return (
    <div className="shell">
      <header className="nav">
        <div className="nav-left">
          <span className="nav-logo-dot" />
          <span className="nav-brand">Supplement Recommender</span>
        </div>
      </header>

      <main className="hero-layout">
        <section className="hero-copy">
          <p className="eyebrow">Using Agents and Knowledge Graphs</p>
          <h1 className="hero-title">
            Personalized Supplement
            <span className="hero-title-accent"> Recommender</span>
          </h1>
          <p className="hero-subtitle">
            An AI-powered system that understands your complete health profile
            and delivers supplement guidance tailored specifically to you – not
            generic advice.
          </p>
          <div className="pill-row">
            <span className="pill pill-green">Neo4j Knowledge Graph</span>
            <span className="pill pill-lilac">LangGraph Agents</span>
            <span className="pill pill-amber">Personalized Health</span>
          </div>
        </section>

        <section className="hero-card">
          <h2 className="card-title">Patient Profile</h2>
          <p className="card-subtitle">
            Tell the system about your current medications, supplements, and
            health context. This profile will be used on the chat page.
          </p>

          <div className="field-group">
            <label>Current Medications</label>
            <textarea
              placeholder="e.g. Warfarin 5mg daily"
              value={profile.medications}
              onChange={(e) => handleChange("medications", e.target.value)}
            />
          </div>

          <div className="field-group">
            <label>Current Supplements</label>
            <textarea
              placeholder="e.g. Fish Oil 1000mg, Vitamin D 2000 IU"
              value={profile.supplements}
              onChange={(e) => handleChange("supplements", e.target.value)}
            />
          </div>

          <div className="field-group">
            <label>Conditions (comma-separated)</label>
            <input
              type="text"
              placeholder="e.g. hypertension, diabetes"
              value={profile.conditions}
              onChange={(e) => handleChange("conditions", e.target.value)}
            />
          </div>

          <div className="field-group">
            <label>Dietary Restrictions (comma-separated)</label>
            <input
              type="text"
              placeholder="e.g. vegan, gluten-free"
              value={profile.dietary_restrictions}
              onChange={(e) =>
                handleChange("dietary_restrictions", e.target.value)
              }
            />
          </div>

          <button className="primary-cta" onClick={goToChat}>
            Continue to Safety Chat
          </button>
        </section>
      </main>
    </div>
  );
}

