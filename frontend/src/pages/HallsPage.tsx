import { useEffect, useState } from "react";
import { api } from "../api/client";

type Hall = { id: number; name: string; rows: number; cols: number; aisle_cols: number[] };
type Pair = {
  id: number;
  hall_id: number;
  row: number;
  left_col: number;
  right_col: number;
  label: string;
};

export default function HallsPage() {
  const [rows, setRows] = useState<Hall[]>([]);
  const [hallId, setHallId] = useState<number | "">("");
  const [pairs, setPairs] = useState<Pair[]>([]);
  const [row, setRow] = useState("");
  const [leftCol, setLeftCol] = useState("");
  const [label, setLabel] = useState("情侣座");
  const [editId, setEditId] = useState<number | null>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api<Hall[]>("/halls").then((hs) => {
      setRows(hs);
      if (hs[0]) setHallId(hs[0].id);
    });
  }, []);

  useEffect(() => {
    if (hallId === "") return;
    api<Pair[]>(`/halls/${hallId}/pairs`).then(setPairs);
  }, [hallId]);

  async function refresh() {
    if (hallId === "") return;
    setPairs(await api<Pair[]>(`/halls/${hallId}/pairs`));
  }

  function resetForm() {
    setRow("");
    setLeftCol("");
    setLabel("情侣座");
    setEditId(null);
  }

  async function submit() {
    setErr("");
    const body = JSON.stringify({ row: Number(row), left_col: Number(leftCol), label });
    try {
      if (editId !== null) {
        await api<Pair>(`/pairs/${editId}`, { method: "PUT", body });
      } else {
        await api<Pair>(`/halls/${hallId}/pairs`, { method: "POST", body });
      }
      resetForm();
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function remove(id: number) {
    setErr("");
    try {
      await api(`/pairs/${id}`, { method: "DELETE" });
      if (editId === id) resetForm();
      await refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  function startEdit(p: Pair) {
    setEditId(p.id);
    setRow(String(p.row));
    setLeftCol(String(p.left_col));
    setLabel(p.label);
    setErr("");
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
          </tr>
        </thead>
        <tbody>
          {rows.map((h) => (
            <tr key={h.id}>
              <td>{h.name}</td>
              <td className="mono">
                {h.rows} × {h.cols}
              </td>
              <td className="mono">{h.aisle_cols.join(", ") || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>情侣对维护</h3>
      <div className="toolbar">
        <label>
          影厅{" "}
          <select value={hallId} onChange={(e) => setHallId(Number(e.target.value))}>
            {rows.map((h) => (
              <option key={h.id} value={h.id}>
                {h.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          排{" "}
          <input value={row} onChange={(e) => setRow(e.target.value)} style={{ width: 56 }} />
        </label>
        <label>
          左列{" "}
          <input
            value={leftCol}
            onChange={(e) => setLeftCol(e.target.value)}
            style={{ width: 56 }}
          />
        </label>
        <label>
          标签{" "}
          <input value={label} onChange={(e) => setLabel(e.target.value)} style={{ width: 96 }} />
        </label>
        <button onClick={submit} disabled={!row || !leftCol}>
          {editId !== null ? "保存修改" : "登记情侣对"}
        </button>
        {editId !== null && <button onClick={resetForm}>取消</button>}
      </div>
      {err && <div className="err">{err}</div>}
      <table className="table">
        <thead>
          <tr>
            <th>排</th>
            <th>列</th>
            <th>标签</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {pairs.map((p) => (
            <tr key={p.id}>
              <td className="mono">R{p.row}</td>
              <td className="mono">
                C{p.left_col}-{p.right_col} ♥
              </td>
              <td>{p.label}</td>
              <td>
                <button onClick={() => startEdit(p)}>编辑</button>{" "}
                <button onClick={() => remove(p.id)}>删除</button>
              </td>
            </tr>
          ))}
          {pairs.length === 0 && (
            <tr>
              <td colSpan={4} className="mono">
                暂无情侣对
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </>
  );
}
