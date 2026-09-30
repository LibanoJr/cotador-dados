import { useState } from "react";
import { API, brl, dataBR, get } from "./api.js";

export default function Cotacao() {
  const [form, setForm] = useState({ regiao: "DF", tipo: "PME", idades: "30, 45, 62", data: "" });
  const [resultado, setResultado] = useState(null);
  const [avisos, setAvisos] = useState([]);
  const [erro, setErro] = useState("");

  const mudar = (campo) => (e) => setForm({ ...form, [campo]: e.target.value });

  async function cotar(e) {
    e.preventDefault();
    const idades = form.idades.split(/[,\s]+/).filter(Boolean);
    if (!idades.length || idades.some((i) => !/^\d+$/.test(i))) {
      return setErro("Informe as idades como números separados por vírgula, por exemplo: 30, 45.");
    }
    setErro("");
    const q = new URLSearchParams({ regiao: form.regiao, tipo: form.tipo, idades: idades.join(",") });
    if (form.data) q.set("data", form.data);
    try {
      const r = await get(`/api/cotacao/?${q}`);
      setResultado(r.resultados);
      setAvisos(r.avisos || []);
    } catch (err) {
      setErro(err.message);
    }
  }

  return (
    <div className="cotacao">
      <form className="filtros" onSubmit={cotar}>
        <label>UF<input value={form.regiao} onChange={mudar("regiao")} maxLength={2} /></label>
        <label>
          Contratação
          <select value={form.tipo} onChange={mudar("tipo")}>
            <option value="PF">Individual/Familiar</option>
            <option value="PME">PME</option>
            <option value="ADESAO">Adesão</option>
          </select>
        </label>
        <label className="largo">Idades das vidas<input value={form.idades} onChange={mudar("idades")} /></label>
        <label>
          Data da cotação
          <input type="date" value={form.data} onChange={mudar("data")} />
        </label>
        <button className="primario">Cotar</button>
      </form>
      <p className="dica">Deixe a data em branco para usar hoje. Datas passadas mostram o preço que valia na época.</p>
      {erro && <p className="msg erro" role="alert">{erro}</p>}
      {avisos.length > 0 && (
        <ul className="avisos-cotacao" aria-label="Planos fora da cotação">
          {avisos.map((a, i) => <li key={i}>{a}</li>)}
        </ul>
      )}
      {resultado && resultado.length === 0 && (
        <p className="vazio">Nenhuma tabela publicada e vigente para esses filtros.</p>
      )}
      {resultado && resultado.length > 0 && (
        <ol className="resultados">
          {resultado.map((r) => (
            <li key={r.tabela_id}>
              <div className="linha-principal">
                <div>
                  <strong>{r.plano}</strong>
                  <span>{r.operadora}{r.coparticipacao ? ", com coparticipação" : ""}</span>
                </div>
                <span className="total">{brl(r.total)}<small>/mês</small></span>
              </div>
              <p className="procedencia">
                Vigente desde {dataBR(r.vigencia_inicio)}
                {r.vigencia_fim ? ` até ${dataBR(r.vigencia_fim)}` : ""}, versão {r.versao}. Fonte: {r.fonte}
                {" ("}
                <a href={`${API}/api/documentos/${r.documento_id}/original/`} target="_blank" rel="noreferrer">
                  ver documento{r.pagina ? `, p. ${r.pagina}` : ""}
                </a>
                {")."}
                {r.verificado_em ? ` Conferido em ${dataBR(r.verificado_em)}.` : ""}
                {r.registro_ans
                  ? ` Registro ANS ${r.registro_ans}${r.conferido_na_ans ? ", conferido na base da ANS." : "."}`
                  : " Sem registro ANS vinculado."}
                {r.fonte_atrasada && <span className="marcador alerta">fonte sem verificação recente</span>}
                {r.liberado_com_justificativa && (
                  <span className="marcador alerta" title={r.liberado_com_justificativa}>
                    acima da referência ANS, confirmado pela equipe
                  </span>
                )}
              </p>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
