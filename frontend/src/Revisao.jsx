import { useCallback, useEffect, useState } from "react";
import { arquivoDeAmostra, brl, dataBR, enviarArquivo, enviarJSON, get, urlArquivo } from "./api.js";

const SEVERIDADE = { erro: "Bloqueia a publicação", alerta: "Confira antes de publicar", info: "Contexto" };
const rotuloSeveridade = (v) => (v.liberavel ? "Exige justificativa" : SEVERIDADE[v.severidade]);
const ACOES = {
  extraida: "extraída do documento",
  valor_corrigido: "valor corrigido",
  publicada: "publicada",
  substituida: "substituída por versão nova",
  rejeitada: "rejeitada",
  bloqueio_liberado: "bloqueio da referência ANS liberado",
  registro_vinculado: "registro ANS vinculado",
  situacao_ans_alterada: "situação do produto mudou na ANS",
};

function descreverAuditoria(a) {
  const d = a.detalhes || {};
  if (a.acao === "valor_corrigido") return ` (faixa ${d.faixa}: ${brl(d.de)} para ${brl(d.para)})`;
  if (a.acao === "bloqueio_liberado") return `. Justificativa: "${d.justificativa}"`;
  if (a.acao === "registro_vinculado") return ` (${d.para})`;
  if (a.acao === "situacao_ans_alterada") return ` (${d.situacao} desde ${dataBR(d.desde)})`;
  return "";
}
const CONTRATACAO = { PF: "Individual/Familiar", PME: "PME", ADESAO: "Adesão" };

function Envio({ aoEnviar }) {
  const [fontes, setFontes] = useState([]);
  const [fonteId, setFonteId] = useState("");
  const [arquivo, setArquivo] = useState(null);
  const [amostras, setAmostras] = useState([]);
  const [amostra, setAmostra] = useState("");
  const [estado, setEstado] = useState({ enviando: false, msg: "", erro: false });

  useEffect(() => {
    get("/api/fontes/").then((todas) => {
      // A fonte ANS é alimentada por sincronização, não por envio de documentos.
      const f = todas.filter((x) => x.tipo !== "ans");
      setFontes(f);
      if (f.length) setFonteId(String(f[0].id));
    }).catch(() => {});
    get("/api/amostras/").then((a) => {
      setAmostras(a.amostras);
      setAmostra(a.sugerida);
    }).catch(() => {});
  }, []);

  async function enviarArquivoPDF(pdf) {
    const dados = new FormData();
    dados.append("arquivo", pdf);
    dados.append("fonte_id", fonteId);
    setEstado({ enviando: true, msg: "" });
    try {
      const r = await enviarArquivo("/api/documentos/enviar/", dados);
      setEstado({ msg: `${r.tabelas.length} tabela(s) extraída(s) e prontas para conferência.` });
      aoEnviar(r.tabelas[0]?.id);
    } catch (err) {
      setEstado({ msg: err.message, erro: true });
    }
  }

  function enviar(e) {
    e.preventDefault();
    if (!arquivo) return setEstado({ msg: "Escolha um PDF ou use uma amostra fictícia abaixo.", erro: true });
    enviarArquivoPDF(arquivo);
  }

  async function enviarAmostra() {
    try {
      await enviarArquivoPDF(await arquivoDeAmostra(amostra));
    } catch (err) {
      setEstado({ msg: err.message, erro: true });
    }
  }

  return (
    <form className="envio" onSubmit={enviar}>
      <h2>Receber material</h2>
      <label>
        Fonte
        <select value={fonteId} onChange={(e) => setFonteId(e.target.value)}>
          {fontes.map((f) => (
            <option key={f.id} value={f.id}>{f.nome}</option>
          ))}
        </select>
      </label>
      <label>
        Arquivo PDF
        <input type="file" accept="application/pdf" onChange={(e) => setArquivo(e.target.files[0])} />
      </label>
      <button className="primario" disabled={estado.enviando}>
        {estado.enviando ? "Extraindo..." : "Enviar e extrair"}
      </button>
      {amostras.length > 0 && (
        <div className="amostras">
          <label>
            Ou use uma amostra fictícia
            <select value={amostra} onChange={(e) => setAmostra(e.target.value)}>
              {amostras.map((a) => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </label>
          <button type="button" disabled={estado.enviando || !amostra} onClick={enviarAmostra}>
            Enviar amostra
          </button>
        </div>
      )}
      {estado.msg && <p className={estado.erro ? "msg erro" : "msg"} role="status">{estado.msg}</p>}
    </form>
  );
}

function Variacao({ pct }) {
  if (pct == null) return <span className="sem-var">nova</span>;
  const largura = Math.min(Math.abs(pct), 50);
  return (
    <span className="variacao">
      <span className="trilho">
        <span className={pct >= 0 ? "barra sobe" : "barra desce"} style={{ width: `${largura}%` }} />
      </span>
      <span className="pct">{pct > 0 ? "+" : ""}{pct.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })}%</span>
    </span>
  );
}

// Aceita "2.466,96", "2466,96", "R$ 2.466,96" e "2466.96". Devolve "2466.96" ou "" se não houver número.
export function paraNumero(texto) {
  let t = String(texto ?? "").replace(/[^\d.,]/g, "");
  if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");
  else if (!/^\d+\.\d{1,2}$/.test(t)) t = t.replace(/\./g, "");
  return t;
}

function LinhaFaixa({ linha, valor, problemas, editavel, aoCorrigir }) {
  const [editando, setEditando] = useState(false);
  const [novo, setNovo] = useState("");
  const [falha, setFalha] = useState("");
  const [salvando, setSalvando] = useState(false);
  const pior = problemas.some((p) => p.severidade === "erro" && !p.liberavel)
    ? "erro"
    : problemas.some((p) => p.liberavel)
      ? "liberavel"
      : problemas.length ? "alerta" : "";

  return (
    <tr className={pior}>
      <th scope="row">{linha.rotulo}</th>
      <td className="num">{brl(linha.anterior)}</td>
      <td className="num">
        {editando ? (
          <form
            className="corrigir"
            onSubmit={async (e) => {
              e.preventDefault();
              const numero = paraNumero(novo);
              if (!numero) return setFalha("Digite um valor, por exemplo 2.466,96");
              setSalvando(true);
              const erro = await aoCorrigir(linha.faixa, numero);
              setSalvando(false);
              // Só fecha a edição se a API aceitou; senão o erro aparece aqui, junto da linha.
              if (erro) setFalha(erro);
              else setEditando(false);
            }}
          >
            <input autoFocus value={novo} onChange={(e) => { setNovo(e.target.value); setFalha(""); }}
              aria-label="Valor corrigido" inputMode="decimal" />
            <button className="primario" disabled={salvando}>{salvando ? "Salvando..." : "Salvar"}</button>
            <button type="button" onClick={() => { setEditando(false); setFalha(""); }}>Cancelar</button>
            {falha && <small className="falha-linha" role="alert">{falha}</small>}
          </form>
        ) : (
          <>
            {brl(linha.novo)}
            {valor?.corrigido_manualmente && <span className="etiqueta">corrigido</span>}
          </>
        )}
      </td>
      <td><Variacao pct={linha.variacao_pct} /></td>
      <td className="acoes-linha">
        {editavel && !editando && (
          <button
            onClick={() => {
              setNovo(linha.novo ? String(linha.novo).replace(".", ",") : "");
              setEditando(true);
            }}
          >
            Corrigir
          </button>
        )}
        {valor?.trecho_origem && <span className="trecho" title={valor.trecho_origem}>origem</span>}
      </td>
    </tr>
  );
}

function Detalhe({ id, revisor, aoMudar }) {
  const [t, setT] = useState(null);
  const [erro, setErro] = useState("");
  const [motivo, setMotivo] = useState("");
  const [justificativa, setJustificativa] = useState("");
  const [registro, setRegistro] = useState("");

  const carregar = useCallback(() => get(`/api/tabelas/${id}/`).then(setT), [id]);
  useEffect(() => {
    setT(null);
    setErro("");
    setJustificativa("");
    setRegistro("");
    carregar();
  }, [carregar]);

  // Devolve "" quando deu certo ou a mensagem de erro, para quem chamou poder mostrá-la no lugar certo.
  async function executar(fn) {
    setErro("");
    try {
      await fn();
      await carregar();
      aoMudar();
      return "";
    } catch (e) {
      setErro(e.message);
      return e.message;
    }
  }

  if (!t) return <p className="vazio">Carregando tabela...</p>;
  const emRevisao = t.status === "em_revisao";
  const valores = Object.fromEntries(t.valores.map((v) => [v.faixa, v]));
  const porFaixa = (f) =>
    t.validacoes.filter((v) => v.severidade !== "info" && (v.faixa === f || (v.faixas || []).includes(f)));
  const precisaJustificar = t.qtd_erros === 0 && t.qtd_liberaveis > 0;
  const exigeRevisor = () => {
    if (!revisor.trim()) throw new Error("Preencha o campo Revisor, no topo, antes de continuar.");
  };

  return (
    <article className="detalhe">
      <header className="ficha">
        <div>
          <h2>{t.plano}</h2>
          <p>
            {t.operadora}. {t.regiao}, {CONTRATACAO[t.tipo_contratacao]}
            {t.coparticipacao ? ", com coparticipação" : ", sem coparticipação"}.
          </p>
        </div>
        <dl>
          <div><dt>Vigência</dt><dd>a partir de {dataBR(t.vigencia_inicio)}</dd></div>
          <div><dt>Fonte</dt><dd>{t.fonte}</dd></div>
          <div>
            <dt>Documento</dt>
            <dd>
              <a href={urlArquivo(t.documento_url)} target="_blank" rel="noreferrer">{t.documento}</a>
              {t.pagina_origem ? `, página ${t.pagina_origem}` : ""}
            </dd>
          </div>
          <div>
            <dt>Registro ANS</dt>
            <dd>
              {t.registro_ans || (emRevisao ? (
                <form
                  className="vincular"
                  onSubmit={(e) => {
                    e.preventDefault();
                    executar(() => {
                      exigeRevisor();
                      return enviarJSON(`/api/planos/${t.plano_id}/registro/`, "PATCH", {
                        registro_ans: registro, usuario: revisor,
                      });
                    });
                  }}
                >
                  <input value={registro} onChange={(e) => setRegistro(e.target.value)}
                    placeholder="000.000/00-0" aria-label="Registro ANS do plano" />
                  <button>Vincular</button>
                </form>
              ) : "não vinculado")}
            </dd>
          </div>
          <div><dt>Situação</dt><dd>{t.status.replace("_", " ")}{t.versao ? `, versão ${t.versao}` : ""}</dd></div>
        </dl>
      </header>

      <table className="razao">
        <caption>
          {t.versao_vigente_id ? "Comparação com a tabela vigente" : "Primeira versão desta tabela"}
        </caption>
        <thead>
          <tr>
            <th scope="col">Faixa etária</th>
            <th scope="col" className="num">Vigente</th>
            <th scope="col" className="num">Extraído</th>
            <th scope="col">Variação</th>
            <th scope="col"><span className="sr">Ações</span></th>
          </tr>
        </thead>
        <tbody>
          {t.comparacao.map((linha) => (
            <LinhaFaixa
              key={linha.faixa}
              linha={linha}
              valor={valores[linha.faixa]}
              problemas={porFaixa(linha.faixa)}
              editavel={emRevisao}
              aoCorrigir={(faixa, valor) =>
                executar(() => {
                  exigeRevisor();
                  return enviarJSON(`/api/tabelas/${id}/valores/`, "PATCH", { faixa, valor, usuario: revisor });
                })
              }
            />
          ))}
        </tbody>
      </table>

      <section className="validacoes" aria-label="Verificações automáticas">
        <h3>Verificações automáticas</h3>
        {t.validacoes.length === 0 && <p className="ok">Nenhum problema encontrado.</p>}
        <ul>
          {t.validacoes.map((v, i) => (
            <li key={i} className={v.liberavel ? "erro liberavel" : v.severidade}>
              <span className="sev">{rotuloSeveridade(v)}</span>
              {v.mensagem}
            </li>
          ))}
        </ul>
      </section>

      {erro && <p className="msg erro" role="alert">{erro}</p>}

      {emRevisao && precisaJustificar && (
        <label className="justificativa">
          Preço fora da banda da referência ANS. Confira o documento original; se o preço estiver certo,
          registre o motivo para publicar mesmo assim.
          <textarea
            value={justificativa}
            onChange={(e) => setJustificativa(e.target.value)}
            rows={2}
            placeholder="Ex.: tabela confirmada com o comercial da operadora em 30/09"
          />
        </label>
      )}

      {emRevisao && (
        <footer className="decisao">
          <button
            className="primario"
            disabled={t.qtd_erros > 0 || (precisaJustificar && !justificativa.trim())}
            title={
              t.qtd_erros > 0
                ? "Corrija os itens que bloqueiam a publicação"
                : precisaJustificar && !justificativa.trim()
                  ? "Escreva a justificativa acima"
                  : ""
            }
            onClick={() =>
              executar(() => {
                exigeRevisor();
                return enviarJSON(`/api/tabelas/${id}/aprovar/`, "POST", { usuario: revisor, justificativa });
              })
            }
          >
            {precisaJustificar ? "Publicar com justificativa" : "Publicar no cotador"}
          </button>
          <input value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Motivo da rejeição" />
          <button
            onClick={() =>
              executar(() => {
                exigeRevisor();
                return enviarJSON(`/api/tabelas/${id}/rejeitar/`, "POST", { usuario: revisor, motivo });
              })
            }
          >
            Rejeitar
          </button>
        </footer>
      )}

      <details className="historico">
        <summary>Histórico desta tabela</summary>
        <ol>
          {t.auditoria.map((a, i) => (
            <li key={i}>
              {new Date(a.criado_em).toLocaleString("pt-BR")}: {ACOES[a.acao] || a.acao}
              {a.usuario ? ` por ${a.usuario}` : ""}
              {descreverAuditoria(a)}
            </li>
          ))}
        </ol>
      </details>
    </article>
  );
}

export default function Revisao({ revisor }) {
  const [fila, setFila] = useState([]);
  const [selecionada, setSelecionada] = useState(null);

  const carregarFila = useCallback(
    () => get("/api/tabelas/?status=em_revisao").then((f) => {
      setFila(f);
      return f;
    }),
    []
  );
  useEffect(() => {
    carregarFila();
  }, [carregarFila]);

  return (
    <div className="revisao">
      <aside className="fila">
        <Envio
          aoEnviar={(id) => carregarFila().then(() => id && setSelecionada(id))}
        />
        <h2>Aguardando conferência <span className="contagem">{fila.length}</span></h2>
        {fila.length === 0 && <p className="vazio">Nada pendente. Envie um PDF acima para começar.</p>}
        <ul>
          {fila.map((t) => (
            <li key={t.id}>
              <button
                className={t.id === selecionada ? "item ativo" : "item"}
                onClick={() => setSelecionada(t.id)}
              >
                <strong>{t.plano}</strong>
                <span>{t.operadora}, vigência {dataBR(t.vigencia_inicio)}</span>
                {t.qtd_erros > 0 && <span className="marcador erro">{t.qtd_erros} bloqueio(s)</span>}
                {t.qtd_erros === 0 && t.qtd_liberaveis > 0 && (
                  <span className="marcador erro">exige justificativa</span>
                )}
                {t.qtd_erros === 0 && !t.qtd_liberaveis && t.qtd_alertas > 0 && (
                  <span className="marcador alerta">{t.qtd_alertas} alerta(s)</span>
                )}
                {t.qtd_erros === 0 && !t.qtd_liberaveis && t.qtd_alertas === 0 && (
                  <span className="marcador ok">sem pendências</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      </aside>
      <section className="area">
        {selecionada ? (
          <Detalhe id={selecionada} revisor={revisor} aoMudar={carregarFila} />
        ) : (
          <p className="vazio">Escolha uma tabela na fila para conferir os valores extraídos.</p>
        )}
      </section>
    </div>
  );
}
