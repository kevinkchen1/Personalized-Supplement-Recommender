import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { PatientProfileProvider } from "./profileContext";
import { ChatPage } from "./pages/ChatPage";

export function App() {
  return (
    <BrowserRouter>
      <PatientProfileProvider>
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </PatientProfileProvider>
    </BrowserRouter>
  );
}

