import RegistrationPage from "./pages/RegistrationPage";
import AdminDashboard from "./pages/AdminDashboard";
import EkycPage from "./pages/EkycPage";
import "./App.css";

function App() {
  const path = window.location.pathname;
  if (path.startsWith("/admin")) return <AdminDashboard />;
  if (path.startsWith("/ekyc")) return <EkycPage />;
  return <RegistrationPage />;
}

export default App;
