import { useState } from "react";

/* ========= QUICK STYLE KNOBS (edit these) ========= */
// Title sizes
const TITLE_LEFT_SIZE  = "28px";    // ← AI Code Reviewer title size
const TITLE_RIGHT_SIZE = "28px";    // ← Chat title size

// FILENAME INPUT (the "snippet.py" box)
// → change border, fontSize, height, width here
const FILENAME_STYLE = {
  width: "90%",             // ← make wider/narrower
  height: 36,               // ← increase/decrease height of box
  padding: "8px 10px",      // ← inner padding
  margin: "8px 0",
  fontSize: "14px",         // ← text size
  fontWeight: 600,          // ← text thickness
  borderRadius: 10,         // ← rounded corners
  border: "2px solid #dbe1ea", // ← BORDER (thickness + color)
  background: "#fff",       // ← background color
  boxSizing: "border-box",  // ← ensures width/height include padding & border
};

// CODE TEXTAREA (the big paste-code box)
// → change border, fontSize, height, width here
const CODE_TEXTAREA_STYLE = {
  width: "90%",             // ← full width of panel
  height: 260,              // ← make taller/shorter
  padding: 8,               // ← space inside box
  fontSize: "14px",         // ← text size
  fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
  borderRadius: 10,         // ← rounded corners
  border: "2px solid #b0c4de", // ← BORDER (change thickness + color)
  background: "#fff",       // ← background color
};

// Page + panels
const PAGE_GRID = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr",
  height: "100vh",
  gap: 0,
};
const PANEL = {
  padding: 16,
  height: "100%",
  boxSizing: "border-box",
  background: "linear-gradient(145deg,#ffffff,#f9fbff)",
};
const CARD_BORDER = "1px solid #dde3ea";

/* =========================
   Left Panel: Code Reviewer
   ========================= */
function ReviewPanel() {
  const [filename, setFilename] = useState("snippet.py");
  const [code, setCode] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function review() {
    setLoading(true); setError(""); setResult(null);
    try {
      const res = await fetch("http://localhost:5001/review", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({ filename, code })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Request failed");
      setResult(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function clearAll() {
    setFilename("snippet.py");
    setCode("");
    setResult(null);
    setError("");
  }

  return (
    <div style={PANEL}>
      {/* TITLE — size controlled by TITLE_LEFT_SIZE */}
      <h1 style={{ margin: 0, fontSize: TITLE_LEFT_SIZE, fontWeight: 700 }}>
        AI Code Reviewer (MVP)
      </h1>

      {/* SNIPPET FILE INPUT (edit in FILENAME_STYLE above) */}
      <input
        value={filename}
        onChange={e => setFilename(e.target.value)}
        placeholder="filename (e.g., script.py)"
        style={FILENAME_STYLE}
      />

      {/* CODE TEXTAREA (edit in CODE_TEXTAREA_STYLE above) */}
      <textarea
        value={code}
        onChange={e => setCode(e.target.value)}
        placeholder='Paste code here, e.g. print("hi")'
        style={CODE_TEXTAREA_STYLE}
      />

      <div style={{display:"flex", alignItems:"center", gap:12, marginTop:8}}>
        <button
          onClick={review}
          disabled={loading || !code.trim()}
          style={{padding:"8px 12px", borderRadius:8, border: CARD_BORDER, background:"#eef2ff"}}
        >
          {loading ? "Reviewing…" : "Review"}
        </button>
        <button
          onClick={clearAll}
          disabled={loading}
          style={{padding:"8px 12px", borderRadius:8, border: CARD_BORDER, background:"#fff"}}
        >
          Clear
        </button>
        <span style={{opacity:0.7}}>{code.length} chars</span>
        {error && <span style={{color:"red"}}>{error}</span>}
      </div>

      {result && (
        <div style={{marginTop:16, border: CARD_BORDER, borderRadius:12, padding:12, background:"#fbfdff"}}>
          <div><b>Summary:</b> {result.summary}</div>

          {/* ▼▼ SCORES SECTION ▼▼ 
              Readability  → how clear & easy the code is
              Complexity   → how difficult logic is
              Security     → possible risks/vulnerabilities
              Testing      → how well it’s covered by tests */}
          <div style={{marginTop:6}}>
            <b>Scores:</b>
            <ul style={{margin: "6px 0 0 18px"}}>
              <li>Readability: {result.scores.readability}</li>
              <li>Complexity: {result.scores.complexity}</li>
              <li>Security: {result.scores.security}</li>
              <li>Testing: {result.scores.testing}</li>
            </ul>
          </div>
          {/* ▲▲ end scores section ▲▲ */}

          {Array.isArray(result.issues) && result.issues.length > 0 && (
            <div style={{marginTop:12}}>
              <b>Issues:</b>
              <ul>
                {result.issues.map((it, i) => (
                  <li key={i}>
                    {it.type}{it.line ? ` (line ${it.line})` : ""}: {it.detail}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* NEW: show program output from backend run */}
          {result.output && (
            <div style={{marginTop:12}}>
              <b>Output:</b>
              <pre
                style={{
                  whiteSpace: "pre-wrap",
                  background: "#fff",
                  border: CARD_BORDER,
                  borderRadius: 8,
                  padding: 8,
                  marginTop: 6
                }}
              >
                {result.output}
              </pre>
            </div>
          )}

          {result.suggestions?.length > 0 && (
            <div style={{marginTop:12}}>
              <b>Suggestions:</b>
              <ul>{result.suggestions.map((s,i)=><li key={i}>{s}</li>)}</ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* =====================
   Right Panel: Chat UI
   ===================== */
function ChatPanel() {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Hi! Ask me about your code or errors." }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  async function send() {
    const text = input.trim();
    if (!text) return;

    const next = [...messages, { role: "user", content: text }];
    setMessages(next);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch("http://localhost:5001/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: next })
      });
      const data = await res.json();
      setMessages(m => [...m, { role: "assistant", content: data.reply || "(no reply)" }]);
    } catch (e) {
      setMessages(m => [...m, { role: "assistant", content: "Error: " + e.message }]);
    } finally {
      setLoading(false);
    }
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div style={{...PANEL, display:"flex", flexDirection:"column"}}>
      {/* TITLE — size controlled by TITLE_RIGHT_SIZE */}
      <h2 style={{ margin: 0, fontSize: TITLE_RIGHT_SIZE, fontWeight: 700 }}>
        Chat
      </h2>

      <div style={{
        flex:1, marginTop:12,
        border: CARD_BORDER, borderRadius:12, padding:8,
        background:"#fff", overflowY:"auto"
      }}>
        {messages.map((m, i) => (
          <div key={i} style={{margin:"6px 0"}}>
            <b>{m.role === "user" ? "You" : "Assistant"}:</b> {m.content}
          </div>
        ))}
      </div>

      <div style={{display:"flex", gap:8, marginTop:8}}>
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Type a question…"
          style={{
            flex:1, height:60, padding:8,
            borderRadius:10, border:"1px solid #dbe1ea", background:"#fff"
          }}
        />
        <button
          onClick={send}
          disabled={loading}
          style={{padding:"8px 12px", borderRadius:8, border: CARD_BORDER, background:"#eef2ff"}}
        >
          {loading ? "Sending…" : "Send"}
        </button>
      </div>
    </div>
  );
}

/* =====================
   Layout: two columns
   ===================== */
export default function App() {
  return (
    <div style={PAGE_GRID}>
      <ReviewPanel />
      <div style={{ borderLeft:"1px solid #eee" }}>
        <ChatPanel />
      </div>
    </div>
  );
}
