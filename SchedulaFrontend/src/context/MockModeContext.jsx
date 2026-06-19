// src/context/MockModeContext.jsx
import { createContext, useContext } from "react";

// Mock mode has been removed: the app always uses real data. This context is
// kept as a no-op so existing consumers (`useMockMode`) keep working without
// changes — `useMock` is always false and toggling does nothing.
const MockModeContext = createContext({
  useMock: false,
  toggleMockMode: () => {},
});

export function MockModeProvider({ children }) {
  return (
    <MockModeContext.Provider value={{ useMock: false, toggleMockMode: () => {} }}>
      {children}
    </MockModeContext.Provider>
  );
}

export function useMockMode() {
  return useContext(MockModeContext);
}

export default MockModeContext;

