import { BrowserRouter, Routes, Route } from "react-router-dom";
import { PatientProfileProvider } from "./profileContext";
import { ProfilePage } from "./pages/ProfilePage";
import { ChatPage } from "./pages/ChatPage";

export function App() {
  return (
    <BrowserRouter>
      <PatientProfileProvider>
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/profile" element={<ProfilePage />} />
        </Routes>
      </PatientProfileProvider>
    </BrowserRouter>
  );
}

