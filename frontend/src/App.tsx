import { Routes, Route } from "react-router-dom";
import StartPage from "./pages/StartPage";
import ResultsPage from "./pages/ResultsPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<StartPage />} />
      <Route path="/results" element={<ResultsPage />} />
    </Routes>
  );
}
