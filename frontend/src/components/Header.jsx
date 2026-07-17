const NAV_ITEMS = [
  { key: "liveness", label: "Liveness Check", href: "/" },
  { key: "ekyc", label: "Full eKYC Demo", href: "/ekyc" },
  { key: "admin", label: "Admin", href: "/admin" },
];

export default function Header({ current }) {
  return (
    <header className="app-header">
      <a className="app-brand" href="/">
        <span className="app-brand-mark" aria-hidden="true">
          eK
        </span>
        eKYC Demo
      </a>
      <nav className="app-nav">
        {NAV_ITEMS.map((item) => (
          <a
            key={item.key}
            href={item.href}
            className={`app-nav-link${current === item.key ? " active" : ""}`}
            aria-current={current === item.key ? "page" : undefined}
          >
            {item.label}
          </a>
        ))}
      </nav>
    </header>
  );
}
