export const API = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

async function tratar(resp) {
  const corpo = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(corpo.erro || `Erro ${resp.status}`);
  return corpo;
}

export const get = (caminho) => fetch(`${API}${caminho}`).then(tratar);

export const enviarJSON = (caminho, metodo, dados) =>
  fetch(`${API}${caminho}`, {
    method: metodo,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(dados),
  }).then(tratar);

export const enviarArquivo = (caminho, formData) =>
  fetch(`${API}${caminho}`, { method: "POST", body: formData }).then(tratar);

export const urlArquivo = (url) => (!url ? null : url.startsWith("http") ? url : `${API}${url}`);

export const brl = (v) =>
  v == null ? "—" : Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });

export const dataBR = (iso) => (iso ? new Date(`${iso.slice(0, 10)}T12:00:00`).toLocaleDateString("pt-BR") : "—");

export async function arquivoDeAmostra(nome) {
  const resp = await fetch(`${API}/api/amostras/${encodeURIComponent(nome)}/`);
  if (!resp.ok) throw new Error(`Não foi possível baixar a amostra ${nome}`);
  return new File([await resp.blob()], nome, { type: "application/pdf" });
}
