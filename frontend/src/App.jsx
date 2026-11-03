import CompletePipelinePage from "./pages/CompletePipelinePage";
import AdminDashboard from "./pages/AdminDashboard";
import "./App.css";

function App() {
  const path = window.location.pathname;
  if (path.startsWith("/admin")) return <AdminDashboard />;
  return <CompletePipelinePage />;
}

export default App;
