import { useEffect, useState } from "react";
import { API, get } from "./api.js";
import Revisao from "./Revisao.jsx";
import Cotacao from "./Cotacao.jsx";
import Fontes from "./Fontes.jsx";

const TELAS = [
  { id: "revisao", nome: "Conferência", componente: Revisao },
  { id: "cotacao", nome: "Cotação", componente: Cotacao },
  { id: "fontes", nome: "Fontes e saúde dos dados", componente: Fontes },
];

export default function App() {
  const [tela, setTela] = useState("revisao");
  const [revisor, setRevisor] = useState("");
  const [apiFora, setApiFora] = useState(false);

  useEffect(() => {
    get("/api/").then(() => setApiFora(false)).catch(() => setApiFora(true));
  }, []);
  const Atual = TELAS.find((t) => t.id === tela).componente;

  useEffect(() => {
    document.title = `${TELAS.find((t) => t.id === tela).nome} | Cotador`;
  }, [tela]);

  return (
    <div className="app">
      <header className="topo">
        <div className="marca">
          <strong>Cotador</strong>
          <span>Central de dados</span>
        </div>
        <nav aria-label="Telas">
          {TELAS.map((t) => (
            <button
              key={t.id}
              className={t.id === tela ? "aba ativa" : "aba"}
              aria-current={t.id === tela ? "page" : undefined}
              onClick={() => setTela(t.id)}
            >
              {t.nome}
            </button>
          ))}
        </nav>
        <label className="revisor">
          Revisor
          <input value={revisor} onChange={(e) => setRevisor(e.target.value)} placeholder="Seu nome" />
        </label>
      </header>
      <p className="aviso-ficticio">Ambiente de demonstração com operadoras e valores fictícios.</p>
      {apiFora && (
        <p className="api-fora" role="alert">
          Não foi possível falar com a API em {API}. Confira se o backend está no ar e se esta origem
          está liberada em CORS_ALLOWED_ORIGINS.
        </p>
      )}
      <main>
        <Atual revisor={revisor} />
      </main>
    </div>
  );
}
