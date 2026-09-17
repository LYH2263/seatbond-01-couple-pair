import { useEffect, useState } from "react";
import { api } from "../api/client";

type Hall = { id: number; name: string; rows: number; cols: number; aisle_cols: number[] };
type Pair = { id: number; hall_id: number; row: number; start_col: number; end_col: number };

export default function HallsPage() {
  const [rows, setRows] = useState<Hall[]>([]);
  const [sel, setSel] = useState<number | null>(null);
  const [pairs, setPairs] = useState<Pair[]>([]);
  const [row, setRow] = useState("");
  const [startCol, setStartCol] = useState("");
  const [editing, setEditing] = useState<Pair | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api<Hall[]>("/halls").then((h) => {
      setRows(h);
      if (h[0]) setSel(h[0].id);
    });
  }, []);

  useEffect(() => {
    if (sel === null) return;
    api<Pair[]>(`/halls/${sel}/pairs`).then(setPairs);
    setEditing(null);
    setErr("");
  }, [sel]);

  const hall = rows.find((h) => h.id === sel) ?? null;

  async function submit() {
    setErr("");
    const body = { row: Number(row), start_col: Number(startCol) };
    try {
      if (editing) {
        await api<Pair>(`/pairs/${editing.id}`, { method: "PUT", body: JSON.stringify(body) });
      } else {
        await api<Pair>(`/halls/${sel}/pairs`, { method: "POST", body: JSON.stringify(body) });
      }
      setRow("");
      setStartCol("");
      setEditing(null);
      setPairs(await api<Pair[]>(`/halls/${sel}/pairs`));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function remove(p: Pair) {
    setErr("");
    try {
      await api<void>(`/pairs/${p.id}`, { method: "DELETE" });
      setPairs(await api<Pair[]>(`/halls/${sel}/pairs`));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <>
      <h2>影厅</h2>
      <table className="table">
        <thead>
          <tr>
            <th>名称</th>
            <th>行×列</th>
            <th>过道列</th>
            <th>情侣对</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((h) => (
            <tr
              key={h.id}
              className={h.id === sel ? "row-sel" : ""}
              style={{ cursor: "pointer" }}
              onClick={() => setSel(h.id)}
            >
              <td>{h.name}</td>
              <td className="mono">
                {h.rows} × {h.cols}
              </td>
              <td className="mono">{h.aisle_cols.join(", ") || "—"}</td>
              <td>{h.id === sel ? `${pairs.length} 对 · 编排中` : "点击编排"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {hall && (
        <div className="pair-panel">
          <h3>
            {hall.name} · 情侣对编排
            <span className="pair-hint">同排相邻两列绑定，锁座须整对写入；不得跨过道</span>
          </h3>
          <table className="table">
            <thead>
              <tr>
                <th>排</th>
                <th>列</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {pairs.map((p) => (
                <tr key={p.id}>
                  <td className="mono">R{p.row}</td>
                  <td className="mono">
                    💑 C{p.start_col}-{p.end_col}
                  </td>
                  <td>
                    <button
                      className="btn-ghost"
                      onClick={() => {
                        setEditing(p);
                        setRow(String(p.row));
                        setStartCol(String(p.start_col));
                      }}
                    >
                      改
                    </button>{" "}
                    <button className="btn-ghost" onClick={() => remove(p)}>
                      删
                    </button>
                  </td>
                </tr>
              ))}
              {pairs.length === 0 && (
                <tr>
                  <td colSpan={3} className="mono">
                    暂无情侣对
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <div className="toolbar">
            <label>
              排{" "}
              <input
                type="number"
                min={1}
                max={hall.rows}
                value={row}
                onChange={(e) => setRow(e.target.value)}
                style={{ width: 72 }}
              />
            </label>
            <label>
              起始列{" "}
              <input
                type="number"
                min={1}
                max={hall.cols - 1}
                value={startCol}
                onChange={(e) => setStartCol(e.target.value)}
                style={{ width: 72 }}
              />
            </label>
            <span className="pair-hint">
              {startCol ? `占用 ${startCol}-${Number(startCol) + 1} 两列` : "占相邻两列"}
            </span>
            <button onClick={submit} disabled={!row || !startCol}>
              {editing ? "保存修改" : "登记情侣对"}
            </button>
            {editing && (
              <button className="btn-ghost" onClick={() => setEditing(null)}>
                取消
              </button>
            )}
          </div>
          {err && <div className="err">{err}</div>}
        </div>
      )}
    </>
  );
}
