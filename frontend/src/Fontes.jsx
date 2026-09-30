import { useCallback, useEffect, useState } from "react";
import { dataBR, enviarJSON, get } from "./api.js";

const TIPOS = {
  api: "API/parceria", planilha: "Planilha", pdf_email: "PDF por e-mail",
  portal: "Portal (RPA)", upload: "Upload manual", ans: "Dados abertos ANS",
};

function ReiniciarDemo({ aoReiniciar }) {
  const [permitido, setPermitido] = useState(false);
  const [estado, setEstado] = useState("");

  useEffect(() => {
    get("/api/").then((r) => setPermitido(r.demo_permite_reiniciar)).catch(() => {});
  }, []);

  if (!permitido) return null;
  return (
    <section className="reiniciar">
      <p>
        A demonstração altera os dados. Para repetir o roteiro do zero, recrie o cenário fictício:
        a linha de base volta publicada e o PDF de junho volta a poder ser enviado.
      </p>
      <button
        disabled={estado === "reiniciando"}
        onClick={async () => {
          if (!window.confirm("Apagar tudo e recriar o cenário fictício de demonstração?")) return;
          setEstado("reiniciando");
          try {
            await enviarJSON("/api/demo/reiniciar/", "POST", {});
            setEstado("Cenário recriado.");
            aoReiniciar();
          } catch (e) {
            setEstado(e.message);
          }
        }}
      >
        {estado === "reiniciando" ? "Recriando..." : "Reiniciar demonstração"}
      </button>
      {estado && estado !== "reiniciando" && <span className="msg" role="status">{estado}</span>}
    </section>
  );
}

export default function Fontes() {
  const [fontes, setFontes] = useState([]);
  const [produtos, setProdutos] = useState([]);
  const [m, setM] = useState(null);

  const carregar = useCallback(() => {
    get("/api/fontes/").then(setFontes);
    get("/api/metricas/").then(setM);
    get("/api/referencia-ans/").then(setProdutos);
  }, []);
  useEffect(carregar, [carregar]);

  return (
    <div className="fontes">
      {m && (
        <dl className="indicadores">
          <div><dt>Tabelas publicadas</dt><dd>{m.tabelas_por_status.publicada || 0}</dd></div>
          <div><dt>Aguardando conferência</dt><dd>{m.fila_em_revisao}</dd></div>
          <div>
            <dt>Valores aceitos sem correção</dt>
            <dd>{m.taxa_aceite_sem_edicao == null ? "—" : `${(m.taxa_aceite_sem_edicao * 100).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`}</dd>
          </div>
          <div><dt>Fontes atrasadas</dt><dd>{m.fontes_atrasadas} de {m.fontes_total}</dd></div>
          <div>
            <dt>Planos ligados ao registro ANS</dt>
            <dd>{m.planos_total - m.planos_sem_registro_ans} de {m.planos_total}</dd>
          </div>
          <div><dt>Bloqueios liberados com justificativa</dt><dd>{m.bloqueios_liberados_com_justificativa}</dd></div>
        </dl>
      )}

      <h2>Catálogo de fontes</h2>
      <table className="tabela-fontes">
        <thead>
          <tr>
            <th scope="col">Fonte</th><th scope="col">Tipo</th><th scope="col">Responsável</th>
            <th scope="col">Atualizar a cada</th><th scope="col">Última verificação</th><th scope="col">Situação</th>
          </tr>
        </thead>
        <tbody>
          {fontes.map((f) => (
            <tr key={f.id}>
              <td>{f.nome}</td>
              <td>{TIPOS[f.tipo] || f.tipo}</td>
              <td>{f.responsavel || "—"}</td>
              <td>{f.frequencia_esperada_dias} dias</td>
              <td>{f.ultima_verificacao ? new Date(f.ultima_verificacao).toLocaleString("pt-BR") : "nunca"}</td>
              <td>
                <span className={f.atrasada ? "marcador alerta" : "marcador ok"}>
                  {f.atrasada ? "atrasada" : "em dia"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2>Referência ANS {m?.referencia_ans_de ? `de ${dataBR(m.referencia_ans_de)}` : ""}</h2>
      <p className="dica">
        Cadastro oficial usado para conferir cada tabela: se o plano existe, se pode ser vendido e qual
        o valor comercial registrado na nota técnica. Dados fictícios nesta demonstração.
      </p>
      <table className="tabela-fontes">
        <thead>
          <tr>
            <th scope="col">Registro</th><th scope="col">Plano</th><th scope="col">Operadora</th>
            <th scope="col">Situação</th>
          </tr>
        </thead>
        <tbody>
          {produtos.map((p) => (
            <tr key={p.registro_ans}>
              <td className="num">{p.registro_ans}</td>
              <td>{p.nome}</td>
              <td>{p.operadora}</td>
              <td>
                <span className={p.situacao === "ativo" ? "marcador ok" : "marcador erro"}>
                  {p.situacao_rotulo}{p.situacao_desde ? ` desde ${dataBR(p.situacao_desde)}` : ""}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <ReiniciarDemo aoReiniciar={carregar} />
    </div>
  );
}
