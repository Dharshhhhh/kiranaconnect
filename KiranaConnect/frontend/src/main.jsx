import React, { useState, useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import {
  Store,
  LayoutDashboard,
  ScanLine,
  Package,
  ShoppingBasket,
  Receipt,
  Wallet,
  Users,
  ChartNoAxesCombined,
  Activity,
  Settings,
  LogOut,
  Menu,
  Bot,
  X,
  ArrowUpRight,
  IndianRupee,
  Bell,
  Upload,
  Send,
  Leaf,
} from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import "./style.css";
import Messenger from "./Messenger.jsx";
import { MessageCircle } from "lucide-react";

const navigation = {
  Dashboard: LayoutDashboard,
  "Shop inbox": MessageCircle,
  "Screenshot Center": ScanLine,
  Inventory: Package,
  Orders: ShoppingBasket,
  "Supplier invoices": Receipt,
  Payments: Wallet,
  Customers: Users,
  Reports: ChartNoAxesCombined,
  "Automation activity": Activity,
  Settings: Settings,
};
const money = (n) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(n);
async function api(path, method = "GET", body) {
  const form = body instanceof FormData;
  const r = await fetch("/api/" + path, {
    method,
    headers: body && !form ? { "Content-Type": "application/json" } : {},
    body: body ? (form ? body : JSON.stringify(body)) : undefined,
  });
  const data = await r.json();
  if (!r.ok)
    throw Error(
      typeof data.detail === "string"
        ? data.detail
        : JSON.stringify(data.detail),
    );
  return data;
}
function Table({ data, columns, empty = "No records yet." }) {
  return (
    <div className="scroll">
      <table>
        <thead>
          <tr>
            {columns.map(([k]) => (
              <th key={k}>{k}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((r, i) => (
            <tr key={r.id ?? i}>
              {columns.map(([k, f]) => (
                <td key={k}>
                  {typeof f === "function" ? f(r) : String(r[f] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {!data.length && <p className="empty">{empty}</p>}
    </div>
  );
}
function Panel({ title, children }) {
  return (
    <section>
      <h2>{title}</h2>
      {children}
    </section>
  );
}
function Badge({ v }) {
  return (
    <span
      className={
        "badge " + (v === "review" || v?.includes("pending") ? "amber" : "")
      }
    >
      {v}
    </span>
  );
}
const examples = [
  "Today’s sales",
  "Low-stock products",
  "Pending invoices",
  "Total inventory value",
  "Create an order for 5 kg rice",
  "Payment history for Meena",
  "Create a purchase order for low-stock items",
  "Summary of today’s activity",
];
function Assistant({ refresh, embedded=false }) {
  const [open, toggle] = useState(false),
    [msg, setMsg] = useState(""),
    [log, setLog] = useState([]),
    [busy, wait] = useState(false);
  const end = useRef(null);
  useEffect(() => end.current?.scrollIntoView({ block: "nearest" }), [log]);
  async function send(text, proposal) {
    if (busy || !text.trim()) return;
    wait(true);
    setMsg("");
    setLog((l) => [...l, { user: true, answer: text }]);
    try {
      const data = await api(
        proposal ? "chat/confirm" : "chat",
        "POST",
        proposal || { message: text },
      );
      setLog((l) => [...l, { ...data, request_id: crypto.randomUUID() }]);
      await refresh();
    } catch (e) {
      setLog((l) => [...l, { answer: e.message }]);
    } finally {
      wait(false);
    }
  }
  return (
    <>
      {(open || embedded) && (
        <div className={embedded?"chat waAi":"chat"}>
          <header>
            <Bot /> KiranaConnect AI Assistant{" "}
            <button hidden={embedded} aria-label="Close assistant" onClick={() => toggle(false)}>
              <X size={18} />
            </button>
          </header>
          <div className="messages">
            {!log.length &&
              examples.map((q) => (
                <button key={q} onClick={() => send(q)}>
                  {q}
                </button>
              ))}
            {log.map((m, i) => (
              <div className={"bubble " + (m.user ? "mine" : "")} key={i}>
                {m.answer}
                {m.confirm && (
                  <>
                    <pre>{JSON.stringify(m.args, null, 2)}</pre>
                    <button
                      disabled={busy || i !== log.length - 1}
                      onClick={() =>
                        send("Confirm", {
                          tool: m.tool,
                          args: m.args,
                          request_id: m.request_id,
                        })
                      }
                    >
                      Confirm
                    </button>
                  </>
                )}
              </div>
            ))}
            <span ref={end} />
          </div>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(msg);
            }}
          >
            <input
              aria-label="Question"
              value={msg}
              onChange={(e) => setMsg(e.target.value)}
              placeholder="Ask about your store"
            />
            <button disabled={busy} aria-label="Send">
              <Send size={17} />
            </button>
          </form>
        </div>
      )}
      <button style={embedded?{display:"none"}:undefined} className="floating" onClick={() => toggle(!open)}>
        <Bot size={20} /> Ask Kirana AI
      </button>
    </>
  );
}
function App() {
  const [user, setUser] = useState(null),
    [state, setState] = useState(null),
    [page, pageTo] = useState("Shop inbox"),
    [notice, setNotice] = useState(""),
    [modal, setModal] = useState(null),
    [mobile, menu] = useState(false);
  const file = useRef(null),
    busy = useRef(false);
  async function refresh() {
    setState(await api("state"));
  }
  useEffect(() => {
    api("me")
      .then(setUser)
      .catch(() => {});
  }, []);
  useEffect(() => {
    if (!user) return;
    const poll = () => refresh().catch((e) => setNotice(e.message));
    poll();
    const id = setInterval(poll, 3000);
    return () => clearInterval(id);
  }, [user]);
  async function action(fn) {
    if (busy.current) return;
    busy.current = true;
    try {
      const message = await fn();
      setNotice(message || "Saved");
      if (user) await refresh();
    } catch (e) {
      setNotice(e.message);
    } finally {
      busy.current = false;
    }
  }
  function go(p) {
    pageTo(p);
    menu(false);
    setModal(null);
  }
  if (!user)
    return (
      <main className="login">
        <div>
          <Store size={42} />
          <h1>KiranaConnect</h1>
          <p>From Screenshot to Action, Powered by AI.</p>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const d = Object.fromEntries(new FormData(e.target));
              action(async () => {
                setUser(await api("login", "POST", d));
                return "Signed in";
              });
            }}
          >
            <label>
              Account
              <select name="name">
                <option>owner</option>

              </select>
            </label>
            <label>
              Password
              <input
                type="password"
                autoComplete="current-password"
                name="password"
                required
              />
            </label>
            <button className="primary">Sign in</button>
          </form>
          <p role="status">{notice}</p><a href="/?customer">Open WhatsApp simulator</a>
        </div>
      </main>
    );
  if (!state) return <main>Loading store… {notice}</main>;
  const { dashboard: d, records, products, jobs } = state,
    owner = user.role === "owner";
  const recColumns = [
    ["Reference", "ref"],
    ["Type", "kind"],
    ["Customer / supplier", "party"],
    ["Amount", (r) => money(r.amount / 100)],
    ["Status", (r) => <Badge v={r.status} />],
  ];
  const jobColumns = [
    [
      "File",
      (j) => (
        <a
          href={"/api/jobs/" + j.id + "/image"}
          target="_blank"
          rel="noreferrer"
        >
          {j.name}
        </a>
      ),
    ],
    ["Source", "source"],
    ["Status", (r) => <Badge v={r.status} />],
    ["Details", "reason"],
    [
      "Review",
      (j) =>
        owner && j.status === "review" ? (
          <button onClick={() => setModal({ type: "review", j })}>
            Review
          </button>
        ) : (
          "—"
        ),
    ],
  ];
  const auditCols = [
    ["Time", "at"],
    ["Actor", "actor"],
    ["Step", "step"],
    ["Details", "detail"],
  ];
  const low = (
    <Table
      data={d.low}
      columns={[
        ["Product", "name"],
        [
          "Available",
          (p) => Number((p.stock - p.reserved).toFixed(3)) + " " + p.unit,
        ],
        ["Restock at", "threshold"],
      ]}
      empty="Stock is above all thresholds."
    />
  );
  const chart = (
    <ResponsiveContainer width="100%" height={230}>
      <AreaChart data={d.chart} margin={{ left: 0, right: 18, top: 15 }}>
        <defs>
          <linearGradient id="green" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#74b789" stopOpacity={0.6} />
            <stop offset="100%" stopColor="#74b789" stopOpacity={0.04} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#e8eee8" vertical={false} />
        <XAxis
          dataKey="day"
          tickFormatter={(v) => v.slice(8)}
          tickLine={false}
        />
        <YAxis width={55} tickLine={false} />
        <Tooltip formatter={money} />
        <Area
          type="monotone"
          dataKey="sales"
          stroke="#26794d"
          fill="url(#green)"
          strokeWidth={3}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
  const metricCards = (
    <div className="cards">
      {[
        ["Sales today", money(d.sales), IndianRupee],
        ["Orders today", d.orders, ShoppingBasket],
        ["Inventory value", money(d.inventory), Package],
        ["Pending payments", money(d.pending), Wallet],
      ].map(([title, val, Icon]) => (
        <section key={title}>
          <Icon size={19} />
          <small>{title}</small>
          <strong>{val}</strong>
        </section>
      ))}
    </div>
  );
  const activeKinds = {
    Orders: ["order", "purchase"],
    "Supplier invoices": ["invoice"],
    Payments: ["payment"],
    Customers: ["credit"],
  };
  return (
    <div className="shell">
      <aside className={mobile ? "shown" : ""}>
        <div className="brand">
          <Store /> KiranaConnect
        </div>
        <small>BUSINESS WORKSPACE</small>
        <nav>
          {Object.entries(navigation).map(([p, Icon]) => (
            <button
              key={p}
              className={p === page ? "selected" : ""}
              onClick={() => go(p)}
            >
              <Icon size={18} />
              {p}
            </button>
          ))}
        </nav>
        <button
          onClick={async () => {
            try {
              await api("logout", "POST");
              setUser(null);
              setState(null);
              setModal(null);
              setNotice("");
            } catch (e) {
              setNotice(e.message);
            }
          }}
        >
          <LogOut size={17} /> Sign out
        </button>
      </aside>
      <main>
        <header className="top">
          <button
            className="mobile"
            onClick={() => menu(!mobile)}
            aria-label="Navigation"
          >
            <Menu />
          </button>
          <span>
            Workspace / <b>{page}</b>
          </span>
          <button
            onClick={() => go("Screenshot Center")}
            aria-label="Screenshot notifications"
          >
            <Bell size={17} />
            {jobs.filter((x) => x.status === "review").length}
          </button>
          <span className="avatar">{user.role[0].toUpperCase()}</span>
        </header>
        <div className="workspace">
          <div className="heading">
            <div>
              <small>
                {new Date().toLocaleDateString("en-IN", {
                  dateStyle: "long",
                  timeZone: "Asia/Kolkata",
                })}
              </small>
              <h1>{page === "Dashboard" ? "Store overview" : page}</h1>
            </div>
            <button className="primary" onClick={() => file.current.click()}>
              <Upload size={16} /> Upload screenshot
            </button>
          </div>
          <input
            ref={file}
            hidden
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={(e) => {
              const f = e.target.files[0];
              e.target.value = "";
              if (f)
                action(async () => {
                  const form = new FormData();
                  form.append("file", f);
                  const j = await api("uploads", "POST", form);
                  go("Screenshot Center");
                  return "Screenshot received · Job " + j.id;
                });
            }}
          />
          {notice && (
            <div className="notice" role="status">
              {notice}
              <button aria-label="Dismiss notice" onClick={() => setNotice("")}>
                <X size={15} />
              </button>
            </div>
          )}
          {page === "Shop inbox" && <><a href="/?customer" target="_blank" rel="noreferrer">Open customer simulator ↗</a><Messenger api={api} shop assistant={<Assistant embedded refresh={refresh}/>} /></>}
          {page === "Dashboard" && (
            <>
              {metricCards}
              <div className="grid2">
                <Panel title="Sales over the last 7 days">{chart}</Panel>
                <Panel title="Low-stock alerts">{low}</Panel>
              </div>
              <Panel title="Recent transactions">
                <Table data={d.recent} columns={recColumns} />
              </Panel>
              <div className="grid2">
                <Panel title="Screenshot notifications">
                  <Table
                    data={d.notifications}
                    columns={jobColumns.filter(([k]) =>
                      ["File", "Status", "Details"].includes(k),
                    )}
                  />
                </Panel>
                <Panel title="Suppliers">
                  <Table
                    data={d.suppliers}
                    columns={[
                      ["Supplier", "party"],
                      ["Invoices", "invoices"],
                      ["Purchases", (r) => money(r.purchases)],
                    ]}
                  />
                </Panel>
              </div>
              <Panel title="Automation activity">
                <Table data={d.activity} columns={auditCols} />
              </Panel>
            </>
          )}
          {page === "Screenshot Center" && (
            <Panel title="Screenshot queue">
              <p>
                Upload an image or copy it into the local inbox. Open a filename
                to inspect the evidence.
              </p>
              <Table data={jobs} columns={jobColumns} />
            </Panel>
          )}
          {page === "Inventory" && (
            <>
              <Panel title="Product catalog">
                {owner && (
                  <button onClick={() => setModal({ type: "product" })}>
                    Add product
                  </button>
                )}
                <Table
                  data={products}
                  columns={[
                    ["Product", "name"],
                    ["Unit", "unit"],
                    ["Buy", (p) => money(p.buy / 100)],
                    ["Sell", (p) => money(p.sell / 100)],
                    ["On hand", "stock"],
                    ["Reserved", "reserved"],
                    ["Restock at", "threshold"],
                    [
                      "Manage",
                      (p) =>
                        owner ? (
                          <button
                            onClick={() => setModal({ type: "product", p })}
                          >
                            Edit
                          </button>
                        ) : (
                          "—"
                        ),
                    ],
                  ]}
                />
              </Panel>
              <Panel title="Restock alerts">{low}</Panel>
              <Panel title="Stock movements">
                <Table
                  data={state.movements}
                  columns={[
                    ["Time", "at"],
                    ["Product", "product"],
                    ["Stock change", "delta"],
                    ["Reserved change", "reservation"],
                    ["Reason", "reason"],
                  ]}
                />
              </Panel>
            </>
          )}
          {activeKinds[page] && (
            <>
              {page === "Customers" && (
                <Panel title="Customer ledger">
                  <Table
                    data={state.customers}
                    columns={[
                      ["Customer", "party"],
                      ["Account balance", (r) => money(r.balance)],
                      ["Entries", "entries"],
                    ]}
                  />
                </Panel>
              )}
              <Panel
                title={page === "Customers" ? "Ledger entries" : "Records"}
              >
                <button
                  onClick={() =>
                    setModal({ type: "record", kind: activeKinds[page][0] })
                  }
                  disabled={page === "Customers" && !owner}
                >
                  {page === "Customers"
                    ? "Add credit entry"
                    : "Create " + activeKinds[page][0]}
                </button>
                <Table
                  data={records.filter((r) =>
                    (page === "Customers"
                      ? ["credit", "payment"]
                      : activeKinds[page]
                    ).includes(r.kind),
                  )}
                  columns={[
                    ...recColumns,
                    [
                      "Action",
                      (r) =>
                        r.status === "reserved" ||
                        r.status === "pending verification" ? (
                          <button
                            onClick={() =>
                              action(async () => {
                                const result = await api(
                                  "records/" + r.id + "/advance",
                                  "POST",
                                );
                                return r.ref + " · " + result.status;
                              })
                            }
                          >
                            {r.status === "reserved"
                              ? "Fulfil order"
                              : "Reconcile"}
                          </button>
                        ) : (
                          "—"
                        ),
                    ],
                  ]}
                />
              </Panel>
            </>
          )}
          {page === "Reports" && (
            <>
              {metricCards}
              <Panel title="Fulfilled sales · INR">
                {chart}
                <Table
                  data={d.chart}
                  columns={[
                    ["Date", "day"],
                    ["Sales", (r) => money(r.sales)],
                  ]}
                />
              </Panel>
            </>
          )}
          {page === "Automation activity" && (
            <Panel title="Audit log">
              <Table data={state.audit} columns={auditCols} />
            </Panel>
          )}
          {page === "Settings" && (
            <Panel title="Store policy">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  const val = e.target.limit.value;
                  action(async () => {
                    await api("settings", "PUT", { invoice_limit: val });
                    return "Invoice policy saved";
                  });
                }}
              >
                <label>
                  Automatic invoice approval limit (₹)
                  <input
                    name="limit"
                    type="number"
                    min="0"
                    step=".01"
                    required
                    defaultValue={state.settings.invoice_limit}
                    disabled={!owner}
                  />
                </label>
                {owner && <button className="primary">Save policy</button>}
              </form>
              <h3>Active integrations</h3>
              {["vision", "chat", "payments"].map((k) => (
                <p key={k}>
                  {k} · <b>{state.settings[k]}</b>
                </p>
              ))}
            </Panel>
          )}
        </div>
      </main>
      {page!=="Shop inbox" && <Assistant refresh={refresh} />}
      {modal && (
        <Editor
          m={modal}
          products={products}
          close={() => setModal(null)}
          action={action}
        />
      )}
    </div>
  );
}
function Editor({ m, products, close, action }) {
  const p = m.p || {},
    [lines, setLines] = useState([
      {
        product: products[0]?.name || "",
        qty: 1,
        price: (products[0]?.buy || 0) / 100,
      },
    ]);
  const [raw, setRaw] = useState(
    m.j
      ? m.j.payload === "{}"
        ? JSON.stringify(
            {
              kind: "payment",
              ref: "",
              party: "",
              amount: null,
              confidence: 1,
              suspicious: false,
            },
            null,
            2,
          )
        : JSON.stringify(JSON.parse(m.j.payload), null, 2)
      : "",
  );
  const [error, setError] = useState("");
  function field(k, label, opts = {}) {
    return (
      <label key={k}>
        {label}
        <input name={k} required {...opts} />
      </label>
    );
  }
  function submit(e) {
    e.preventDefault();
    const fields = Object.fromEntries(new FormData(e.target));
    action(async () => {
      try {
        let msg = "Saved";
        if (m.type === "product")
          await api(
            "products" + (p.id ? "/" + p.id : ""),
            p.id ? "PUT" : "POST",
            fields,
          );
        if (m.type === "record") {
          const items = ["order", "invoice"].includes(m.kind)
            ? lines.map((l) => ({
                product: l.product,
                unit: products.find((p) => p.name === l.product)?.unit,
                qty: l.qty,
                ...(m.kind === "invoice" ? { price: l.price } : {}),
              }))
            : [];
          await api("records", "POST", { ...fields, kind: m.kind, items });
        }
        if (m.type === "review") {
          const r = await api(
            "jobs/" + m.j.id + "/review",
            "POST",
            JSON.parse(raw),
          );
          msg = r.status + " · " + r.reason;
          if (r.status === "review") throw Error(msg);
        }
        close();
        return msg;
      } catch (e) {
        setError(e.message);
        throw e;
      }
    });
  }
  return (
    <div className="overlay">
      <div className="dialog" role="dialog" aria-modal="true">
        <header>
          <h2>
            {m.type === "product"
              ? p.id
                ? "Edit product"
                : "Add product"
              : m.type === "review"
                ? "Review screenshot"
                : "Create " + m.kind}
          </h2>
          <button onClick={close} aria-label="Close">
            <X size={18} />
          </button>
        </header>
        {error && (
          <p role="alert" className="notice">
            {error}
          </p>
        )}
        <form onSubmit={submit}>
          {m.type === "product" && (
            <>
              {field("name", "Product name", { defaultValue: p.name })}
              <label>
                Unit
                <select name="unit" defaultValue={p.unit}>
                  {["kg", "piece", "litre", "pack"].map((v) => (
                    <option key={v}>{v}</option>
                  ))}
                </select>
              </label>
              {[
                ["buy", "Buying price (₹)"],
                ["sell", "Selling price (₹)"],
                ["stock", "On hand"],
                ["threshold", "Restock threshold"],
              ].map(([k, title]) =>
                field(k, title, {
                  type: "number",
                  min: 0,
                  step: ["buy", "sell"].includes(k) ? ".01" : ".001",
                  defaultValue:
                    p[k] === undefined
                      ? ""
                      : p[k] / (["buy", "sell"].includes(k) ? 100 : 1),
                }),
              )}
            </>
          )}
          {m.type === "record" && (
            <>
              {field("ref", "Document / transaction reference")}
              {field("party", m.kind === "invoice" ? "Supplier" : "Customer")}
              {m.kind !== "order" &&
                field("amount", "Document total (₹)", {
                  type: "number",
                  min: ".01",
                  step: ".01",
                })}
              {["order", "invoice"].includes(m.kind) && (
                <>
                  {lines.map((l, i) => {
                    const change = (k, v) =>
                      setLines(
                        lines.map((x, j) => (j === i ? { ...x, [k]: v } : x)),
                      );
                    return (
                      <fieldset key={i}>
                        <label>
                          Product
                          <select
                            value={l.product}
                            onChange={(e) => change("product", e.target.value)}
                          >
                            {products.map((p) => (
                              <option key={p.id}>{p.name}</option>
                            ))}
                          </select>
                        </label>
                        <label>
                          Quantity (
                          {products.find((p) => p.name === l.product)?.unit})
                          <input
                            required
                            type="number"
                            min=".001"
                            step=".001"
                            value={l.qty}
                            onChange={(e) => change("qty", e.target.value)}
                          />
                        </label>
                        {m.kind === "invoice" && (
                          <label>
                            Unit price (₹)
                            <input
                              required
                              type="number"
                              min=".01"
                              step=".01"
                              value={l.price}
                              onChange={(e) => change("price", e.target.value)}
                            />
                          </label>
                        )}
                        {lines.length > 1 && (
                          <button
                            type="button"
                            onClick={() =>
                              setLines(lines.filter((_, j) => j !== i))
                            }
                          >
                            Remove line
                          </button>
                        )}
                      </fieldset>
                    );
                  })}
                  <button
                    type="button"
                    onClick={() =>
                      setLines([
                        ...lines,
                        { product: products[0]?.name || "", qty: 1, price: "" },
                      ])
                    }
                  >
                    Add line
                  </button>
                </>
              )}
            </>
          )}
          {m.type === "review" && (
            <>
              <img
                src={"/api/jobs/" + m.j.id + "/image"}
                alt="Original screenshot"
              />
              <p>{m.j.reason}</p>
              <label>
                Correct the extracted proposal against the image
                <textarea
                  rows={11}
                  value={raw}
                  onChange={(e) => setRaw(e.target.value)}
                />
              </label>
              <button
                type="button"
                onClick={() =>
                  action(async () => {
                    await api("jobs/" + m.j.id + "/review", "POST", {
                      reject: true,
                    });
                    close();
                    return "Screenshot rejected";
                  })
                }
              >
                Reject screenshot
              </button>
            </>
          )}
          <button className="primary">
            {m.type === "review" ? "Validate and approve" : "Save"}
          </button>
          {p.id && (
            <button
              type="button"
              onClick={() =>
                action(async () => {
                  await api("products/" + p.id, "DELETE");
                  close();
                  return "Product archived";
                })
              }
            >
              Archive product
            </button>
          )}
        </form>
      </div>
    </div>
  );
}
createRoot(document.getElementById("root")).render(new URLSearchParams(location.search).has("customer") ? <Messenger api={api}/> : <App />);
