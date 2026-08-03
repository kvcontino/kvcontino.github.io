import { useState } from "react";

const data = {
  machine: {
    name: "Dell Precision 3630 Tower",
    specs: ["Ubuntu (or Proxmox)", "16 GB RAM", "1 TB SSD", "PCIe expansion slots", "Workstation-class CPU"],
  },
  architecture: [
    {
      id: "docker",
      label: "Docker Compose on Ubuntu",
      rec: true,
      summary: "Each service runs in an isolated container on bare metal Ubuntu. One YAML file per stack. Simple, widely documented, low overhead.",
      pros: ["Least abstraction", "Fast to deploy", "Community support is vast", "Easy to back up (volume dirs)"],
      cons: ["No VM isolation", "Harder to experiment without affecting running services"],
      config: [
        "Install Docker + Docker Compose plugin",
        "One compose file per service group (e.g. media.yml, network.yml)",
        "Mount /opt/appdata as persistent volume root",
        "Use .env files for secrets — never hardcode in compose",
        "Enable UFW; expose only ports you intend to",
      ],
    },
    {
      id: "proxmox",
      label: "Proxmox Hypervisor",
      rec: false,
      summary: "Wipe Ubuntu, run Proxmox bare metal. Spin LXC containers or full VMs per service group. Snapshot before any major change.",
      pros: ["Snapshot / rollback any VM", "True isolation between services", "Web UI for all VM management", "Good for learning infra concepts"],
      cons: ["More overhead to set up", "Overkill if you just want services running", "Adds a management layer to maintain"],
      config: [
        "Flash Proxmox ISO to USB, install over Ubuntu",
        "Use LXC containers (not VMs) for lightweight services",
        "Run Docker inside a single privileged LXC for simplicity",
        "Or isolate by concern: media LXC, network LXC, AI LXC",
        "ZFS optional — skip it on a single SSD",
      ],
    },
  ],
  functions: [
    {
      id: "media",
      label: "Media Server",
      icon: "▶",
      color: "#e85d04",
      summary: "Stream video, music, and photos to any device on your network or remotely.",
      tools: [
        {
          name: "Jellyfin",
          role: "Primary media server",
          why: "Fully free, no account required, active development. Plex alternative with no telemetry.",
          config: [
            "Mount media directory as read-only volume",
            "Set transcoding temp dir to /tmp (RAM-backed) to reduce SSD writes",
            "Hardware transcoding available if you have a Quadro/Intel iGPU",
            "Port 8096 (HTTP), 8920 (HTTPS)",
          ],
        },
        {
          name: "Kavita",
          role: "Comics / ebooks",
          why: "If you have comics, manga, or ebooks — Kavita handles them well where Jellyfin doesn't.",
          config: ["Mount library dir", "Port 5000", "Runs alongside Jellyfin without conflict"],
        },
      ],
      ssdNote: "Configure Jellyfin transcode dir to RAM (/dev/shm or tmpfs) to avoid high write load on SSD.",
    },
    {
      id: "cloud",
      label: "Personal Cloud",
      icon: "☁",
      color: "#0077b6",
      summary: "Replace Google Drive, Dropbox, and Google Photos with self-hosted equivalents.",
      tools: [
        {
          name: "Nextcloud",
          role: "Files, calendar, contacts, photos",
          why: "The most complete self-hosted cloud suite. Replaces Google Drive + Calendar + Contacts in one.",
          config: [
            "Use nextcloud:fpm image + Nginx reverse proxy for best performance",
            "Or use nextcloud:apache image for simplicity",
            "PostgreSQL recommended over SQLite at this scale",
            "Enable Memories app for photo management (replaces Google Photos)",
            "Port 443 via reverse proxy (Caddy or Nginx)",
          ],
        },
        {
          name: "Immich",
          role: "Google Photos replacement",
          why: "If you only want photos/video backup with ML-based face/object recognition, Immich is sharper than Nextcloud Memories.",
          config: ["Requires Redis + PostgreSQL (included in official compose)", "Port 2283", "Mobile app available"],
        },
      ],
      ssdNote: "Main write load is syncing files. 1TB should be fine unless you're syncing RAW photos at scale.",
    },
    {
      id: "security",
      label: "Passwords & Secrets",
      icon: "🔑",
      color: "#7209b7",
      summary: "Self-hosted password manager. Eliminates dependency on 1Password, Bitwarden cloud, etc.",
      tools: [
        {
          name: "Vaultwarden",
          role: "Bitwarden-compatible server",
          why: "Runs the full Bitwarden protocol on ~10MB RAM. Use official Bitwarden clients (browser ext, mobile) against your own server.",
          config: [
            "Set SIGNUPS_ALLOWED=false after creating your account",
            "Enable HTTPS — browsers will refuse HTTP for password managers",
            "Use Caddy as reverse proxy for automatic TLS",
            "Port 80/443 via reverse proxy",
            "Back up /vaultwarden/data/ daily — this is your only copy",
          ],
        },
      ],
      ssdNote: "Negligible write load.",
    },
    {
      id: "network",
      label: "Network Services",
      icon: "⬡",
      color: "#2d6a4f",
      summary: "Network-wide ad blocking, private DNS, and a VPN to reach your home network from anywhere.",
      tools: [
        {
          name: "Pi-hole + Unbound",
          role: "DNS sinkhole + recursive resolver",
          why: "Pi-hole blocks ads/trackers for every device on your network. Unbound makes it a full recursive DNS resolver — no upstream provider sees your queries.",
          config: [
            "Run on a static IP — set as DNS server in your router",
            "Unbound listens on 5335, Pi-hole forwards to it",
            "Use macvlan networking in Docker so Pi-hole gets its own IP",
            "Port 53 (DNS), 80 (admin UI)",
            "Whitelist aggressively at first — some blocklists are too broad",
          ],
        },
        {
          name: "WireGuard (via wg-easy)",
          role: "Home VPN",
          why: "Access your home network from anywhere. Also routes your traffic through home when on untrusted networks.",
          config: [
            "Requires port forwarding on your router: UDP 51820",
            "wg-easy gives you a web UI for client management",
            "Generate QR codes for mobile clients",
            "Set DNS to your Pi-hole IP inside tunnel for ad blocking on mobile",
          ],
        },
        {
          name: "Nginx Proxy Manager",
          role: "Reverse proxy + TLS",
          why: "Routes external traffic to internal services by subdomain. Handles Let's Encrypt TLS automatically. Required if you expose anything to the internet.",
          config: [
            "Point your domain's DNS to your home IP",
            "Enable DDNS (Dynamic DNS) if your ISP changes your IP — use Cloudflare + ddclient",
            "Create proxy hosts per service: jellyfin.yourdomain.com → localhost:8096",
          ],
        },
      ],
      ssdNote: "Pi-hole writes query logs. Set log retention to 2–7 days to limit SSD writes.",
    },
    {
      id: "docs",
      label: "Document Management",
      icon: "⊞",
      color: "#c77dff",
      summary: "Ingest, OCR, tag, and search physical and digital documents.",
      tools: [
        {
          name: "Paperless-ngx",
          role: "Document archive with OCR",
          why: "Scan or drag in PDFs, images of documents, etc. OCR makes them full-text searchable. Replaces filing cabinets and manual organization.",
          config: [
            "Set up a 'consume' directory — drop files there and they auto-import",
            "Integrates with scanners that support scan-to-folder/email",
            "Uses Redis + PostgreSQL (included in compose)",
            "Port 8000",
            "Tag taxonomy is worth planning before you import 500 documents",
          ],
        },
      ],
      ssdNote: "Moderate writes during bulk import/OCR. Normal usage is low.",
    },
    {
      id: "code",
      label: "Private Git",
      icon: "⌥",
      color: "#4361ee",
      summary: "Self-hosted Git for personal projects, dotfiles, configs, and anything you don't want on GitHub.",
      tools: [
        {
          name: "Gitea",
          role: "Lightweight Git server",
          why: "Full GitHub-like UI, issues, PRs, webhooks. Runs on ~50MB RAM. Forgejo is the community fork if you prefer.",
          config: [
            "SQLite is fine for personal use",
            "Port 3000 (web), 22 (SSH — remap host SSH to another port first)",
            "Enable LFS if storing large files",
          ],
        },
      ],
      ssdNote: "Negligible unless storing large binary assets in LFS.",
    },
    {
      id: "ai",
      label: "Local AI",
      icon: "◈",
      color: "#f72585",
      summary: "Run LLMs locally. No data leaves the machine. Depends heavily on whether you have a discrete GPU.",
      tools: [
        {
          name: "Ollama",
          role: "LLM runtime",
          why: "Pulls and runs quantized models with one command. Exposes an API compatible with OpenAI clients.",
          config: [
            "GPU: install nvidia-container-toolkit, pass GPU to container",
            "CPU-only: works but limit models to 7B or smaller (slow otherwise)",
            "Recommended models without GPU: llama3.2:3b, phi3:mini",
            "With GPU (8GB VRAM+): llama3.1:8b, mistral, gemma2",
            "Port 11434",
          ],
        },
        {
          name: "Open WebUI",
          role: "Chat interface for Ollama",
          why: "Browser-based UI that connects to Ollama. Supports conversation history, model switching, RAG.",
          config: ["Set OLLAMA_BASE_URL to your Ollama container", "Port 3000 (remap if Gitea is also running)"],
        },
      ],
      ssdNote: "Models are large (4–20GB each). Budget 50–100GB if you run several. No unusual write patterns.",
    },
  ],
};

const Tag = ({ children, color }) => (
  <span
    style={{
      background: color + "22",
      color: color,
      border: `1px solid ${color}44`,
      padding: "2px 8px",
      borderRadius: "2px",
      fontSize: "10px",
      fontFamily: "'IBM Plex Mono', monospace",
      letterSpacing: "0.05em",
      textTransform: "uppercase",
    }}
  >
    {children}
  </span>
);

const ConfigList = ({ items }) => (
  <ul style={{ margin: "8px 0 0 0", padding: 0, listStyle: "none" }}>
    {items.map((item, i) => (
      <li
        key={i}
        style={{
          display: "flex",
          gap: "8px",
          padding: "4px 0",
          fontSize: "12px",
          color: "#94a3b8",
          borderBottom: "1px solid #1e293b",
          fontFamily: "'IBM Plex Mono', monospace",
        }}
      >
        <span style={{ color: "#475569", flexShrink: 0 }}>{String(i + 1).padStart(2, "0")}</span>
        <span>{item}</span>
      </li>
    ))}
  </ul>
);

const ToolCard = ({ tool }) => {
  const [open, setOpen] = useState(false);
  return (
    <div
      style={{
        background: "#0f172a",
        border: "1px solid #1e293b",
        borderRadius: "4px",
        marginBottom: "8px",
        overflow: "hidden",
      }}
    >
      <div
        onClick={() => setOpen(!open)}
        style={{
          padding: "10px 14px",
          cursor: "pointer",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: "12px",
        }}
      >
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "4px" }}>
            <span style={{ color: "#f8fafc", fontWeight: 700, fontSize: "13px", fontFamily: "'IBM Plex Mono', monospace" }}>
              {tool.name}
            </span>
            <span style={{ color: "#64748b", fontSize: "11px" }}>— {tool.role}</span>
          </div>
          <p style={{ margin: 0, color: "#64748b", fontSize: "12px", lineHeight: 1.5 }}>{tool.why}</p>
        </div>
        <span style={{ color: "#334155", fontSize: "14px", flexShrink: 0, marginTop: "2px" }}>{open ? "▲" : "▼"}</span>
      </div>
      {open && (
        <div style={{ padding: "0 14px 12px", borderTop: "1px solid #1e293b" }}>
          <div style={{ paddingTop: "10px" }}>
            <span style={{ color: "#475569", fontSize: "10px", textTransform: "uppercase", letterSpacing: "0.1em", fontFamily: "'IBM Plex Mono', monospace" }}>
              Configuration
            </span>
            <ConfigList items={tool.config} />
          </div>
        </div>
      )}
    </div>
  );
};

const FunctionCard = ({ fn, isActive, onClick }) => (
  <div
    onClick={onClick}
    style={{
      padding: "14px 16px",
      border: `1px solid ${isActive ? fn.color + "66" : "#1e293b"}`,
      borderLeft: `3px solid ${isActive ? fn.color : "#1e293b"}`,
      background: isActive ? fn.color + "0d" : "#0a0f1a",
      borderRadius: "4px",
      cursor: "pointer",
      transition: "all 0.15s",
      marginBottom: "6px",
    }}
  >
    <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
      <span style={{ color: fn.color, fontSize: "16px", width: "20px", textAlign: "center" }}>{fn.icon}</span>
      <span style={{ color: "#f8fafc", fontSize: "13px", fontWeight: 600, fontFamily: "'IBM Plex Mono', monospace" }}>{fn.label}</span>
    </div>
    <p style={{ margin: "6px 0 0 30px", color: "#475569", fontSize: "11px", lineHeight: 1.5 }}>{fn.summary}</p>
  </div>
);

export default function Dashboard() {
  const [activeFunction, setActiveFunction] = useState(data.functions[0].id);
  const [activeArch, setActiveArch] = useState("docker");

  const fn = data.functions.find((f) => f.id === activeFunction);
  const arch = data.architecture.find((a) => a.id === activeArch);

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#070b12",
        color: "#f8fafc",
        fontFamily: "'IBM Plex Sans', sans-serif",
        padding: "0",
      }}
    >
      <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;700&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap" rel="stylesheet" />

      {/* Header */}
      <div style={{ borderBottom: "1px solid #1e293b", padding: "20px 28px 16px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "12px" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "6px" }}>
              <div style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#22c55e", boxShadow: "0 0 8px #22c55e" }} />
              <span style={{ color: "#64748b", fontSize: "11px", fontFamily: "'IBM Plex Mono', monospace", letterSpacing: "0.1em", textTransform: "uppercase" }}>
                Project Dashboard
              </span>
            </div>
            <h1 style={{ margin: 0, fontSize: "20px", fontWeight: 600, color: "#f8fafc", letterSpacing: "-0.02em" }}>
              {data.machine.name}
            </h1>
          </div>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
            {data.machine.specs.map((s, i) => (
              <span
                key={i}
                style={{
                  background: "#0f172a",
                  border: "1px solid #1e293b",
                  color: "#64748b",
                  padding: "3px 10px",
                  borderRadius: "2px",
                  fontSize: "11px",
                  fontFamily: "'IBM Plex Mono', monospace",
                }}
              >
                {s}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: 0, minHeight: "calc(100vh - 80px)" }}>
        {/* Sidebar */}
        <div style={{ borderRight: "1px solid #1e293b", padding: "20px 16px" }}>
          <div style={{ marginBottom: "24px" }}>
            <div style={{ color: "#334155", fontSize: "10px", fontFamily: "'IBM Plex Mono', monospace", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: "10px", paddingLeft: "4px" }}>
              Functions
            </div>
            {data.functions.map((fn) => (
              <FunctionCard
                key={fn.id}
                fn={fn}
                isActive={activeFunction === fn.id}
                onClick={() => setActiveFunction(fn.id)}
              />
            ))}
          </div>
        </div>

        {/* Main Content */}
        <div style={{ padding: "24px 28px", overflowY: "auto" }}>
          {/* Architecture Selector */}
          <div style={{ marginBottom: "28px" }}>
            <div style={{ color: "#334155", fontSize: "10px", fontFamily: "'IBM Plex Mono', monospace", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: "12px" }}>
              Architecture
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
              {data.architecture.map((a) => (
                <div
                  key={a.id}
                  onClick={() => setActiveArch(a.id)}
                  style={{
                    padding: "14px 16px",
                    border: `1px solid ${activeArch === a.id ? "#3b82f6aa" : "#1e293b"}`,
                    background: activeArch === a.id ? "#3b82f60d" : "#0a0f1a",
                    borderRadius: "4px",
                    cursor: "pointer",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
                    <span style={{ color: "#f8fafc", fontWeight: 600, fontSize: "13px", fontFamily: "'IBM Plex Mono', monospace" }}>{a.label}</span>
                    {a.rec && <Tag color="#22c55e">Recommended</Tag>}
                  </div>
                  <p style={{ margin: "0 0 10px", color: "#64748b", fontSize: "12px", lineHeight: 1.5 }}>{a.summary}</p>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px" }}>
                    <div>
                      <div style={{ color: "#22c55e", fontSize: "10px", fontFamily: "'IBM Plex Mono', monospace", marginBottom: "4px" }}>PROS</div>
                      {a.pros.map((p, i) => <div key={i} style={{ color: "#475569", fontSize: "11px", paddingBottom: "2px" }}>+ {p}</div>)}
                    </div>
                    <div>
                      <div style={{ color: "#f43f5e", fontSize: "10px", fontFamily: "'IBM Plex Mono', monospace", marginBottom: "4px" }}>CONS</div>
                      {a.cons.map((c, i) => <div key={i} style={{ color: "#475569", fontSize: "11px", paddingBottom: "2px" }}>− {c}</div>)}
                    </div>
                  </div>
                  {activeArch === a.id && (
                    <div style={{ marginTop: "12px", borderTop: "1px solid #1e293b", paddingTop: "10px" }}>
                      <div style={{ color: "#334155", fontSize: "10px", fontFamily: "'IBM Plex Mono', monospace", marginBottom: "6px", textTransform: "uppercase", letterSpacing: "0.1em" }}>Setup Steps</div>
                      <ConfigList items={a.config} />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Active Function Detail */}
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "16px" }}>
              <span style={{ color: fn.color, fontSize: "20px" }}>{fn.icon}</span>
              <div>
                <h2 style={{ margin: 0, fontSize: "16px", fontWeight: 600, color: "#f8fafc", letterSpacing: "-0.01em" }}>{fn.label}</h2>
                <p style={{ margin: 0, color: "#64748b", fontSize: "12px" }}>{fn.summary}</p>
              </div>
            </div>

            {fn.ssdNote && (
              <div style={{ background: "#0f172a", border: "1px solid #854d0e44", borderLeft: "3px solid #ca8a04", borderRadius: "4px", padding: "10px 14px", marginBottom: "16px", display: "flex", gap: "10px" }}>
                <span style={{ color: "#ca8a04", fontSize: "12px", flexShrink: 0 }}>⚠</span>
                <span style={{ color: "#92400e", fontSize: "12px", fontFamily: "'IBM Plex Mono', monospace" }}>SSD: {fn.ssdNote}</span>
              </div>
            )}

            <div style={{ color: "#334155", fontSize: "10px", fontFamily: "'IBM Plex Mono', monospace", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: "10px" }}>
              Tools — click to expand config
            </div>
            {fn.tools.map((tool, i) => (
              <ToolCard key={i} tool={tool} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
