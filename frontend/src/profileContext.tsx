import {
  createContext,
  useContext,
  useState,
  ReactNode,
  Dispatch,
  SetStateAction,
} from "react";

export type PatientProfile = {
  medications: string;
  supplements: string;
  conditions: string;
  dietary_restrictions: string;
};

type PatientProfileContextValue = {
  profile: PatientProfile;
  setProfile: Dispatch<SetStateAction<PatientProfile>>;
};

const PatientProfileContext = createContext<PatientProfileContextValue | null>(
  null,
);

export function PatientProfileProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<PatientProfile>({
    medications: "",
    supplements: "",
    conditions: "",
    dietary_restrictions: "",
  });

  return (
    <PatientProfileContext.Provider value={{ profile, setProfile }}>
      {children}
    </PatientProfileContext.Provider>
  );
}

export function usePatientProfile() {
  const ctx = useContext(PatientProfileContext);
  if (!ctx) {
    throw new Error("usePatientProfile must be used within PatientProfileProvider");
  }
  return ctx;
}

