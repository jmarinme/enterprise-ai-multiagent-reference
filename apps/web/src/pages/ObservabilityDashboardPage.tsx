import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import type { AccountInfo, IPublicClientApplication } from "@azure/msal-browser";
import { getAccessToken } from "../auth/getAccessToken";
import {
  getSummaryKpis,
  listObservabilityConversations,
  ObservabilityRequestError,
} from "../api/observability";
import type { ConversationSummaryRow, ObservabilityFilters, SummaryKpis } from "../api/observability";
import "./observability.css";

const PAGE_SIZE = 25;

interface ObservabilityDashboardPageProps {
  instance: IPublicClientApplication;
  account: AccountInfo;
}

function formatUnavailable(value: number | null | undefined, formatter?: (n: number) => string): string {
  if (value === null || value === undefined) {
    return "No disponible";
  }
  return formatter ? formatter(value) : String(value);
}

function formatCost(value: number | null | undefined): string {
  return formatUnavailable(value, (n) => `$${n.toFixed(4)}`);
}

function formatPercent(value: number | null | undefined): string {
  return formatUnavailable(value, (n) => `${(n * 100).toFixed(1)}%`);
}

function formatMs(value: number | null | undefined): string {
  return formatUnavailable(value, (n) => `${Math.round(n)} ms`);
}

export function ObservabilityDashboardPage({ instance, account }: ObservabilityDashboardPageProps) {
  const [kpis, setKpis] = useState<SummaryKpis | null>(null);
  const [rows, setRows] = useState<ConversationSummaryRow[]>([]);
  const [total, setTotal] = useState(0);
  const [skip, setSkip] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [errorStatus, setErrorStatus] = useState<number | null>(null);
  const [filters, setFilters] = useState<ObservabilityFilters>({});

  useEffect(() => {
    let cancelled = false;

    async function load(): Promise<void> {
      setIsLoading(true);
      setErrorStatus(null);
      try {
        const accessToken = await getAccessToken(instance, account);
        const [kpisResult, conversationsResult] = await Promise.all([
          getSummaryKpis(accessToken, filters),
          listObservabilityConversations(accessToken, filters, { skip, limit: PAGE_SIZE }),
        ]);
        if (cancelled) return;
        setKpis(kpisResult);
        setRows(conversationsResult.items);
        setTotal(conversationsResult.total);
      } catch (error) {
        if (cancelled) return;
        if (error instanceof ObservabilityRequestError) {
          setErrorStatus(error.status);
        } else {
          console.error("Observability dashboard load failed:", error);
          setErrorStatus(0);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [skip, filters]);

  function handleSearchSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const formData = new FormData(event.currentTarget);
    const search = String(formData.get("search") ?? "").trim();
    setSkip(0);
    setFilters((current) => ({ ...current, search: search || undefined }));
  }

  return (
    <main className="observability-dashboard">
      <h1 className="observability-dashboard__title">Observability</h1>

      {errorStatus === 403 && (
        <p className="observability-dashboard__error">
          No tienes autorización para ver Observability.
        </p>
      )}
      {errorStatus !== null && errorStatus !== 403 && (
        <p className="observability-dashboard__error">
          No se pudieron cargar los datos de observabilidad. Intenta de nuevo más tarde.
        </p>
      )}

      <section className="observability-kpis" aria-label="Indicadores principales">
        <KpiCard label="Conversaciones" value={formatUnavailable(kpis?.conversationCount)} />
        <KpiCard label="Runs" value={formatUnavailable(kpis?.runCount)} />
        <KpiCard label="Tasa de éxito" value={formatPercent(kpis?.successRate)} />
        <KpiCard label="Latencia promedio" value={formatMs(kpis?.averageLatencyMs)} />
        <KpiCard label="Tokens de entrada" value={formatUnavailable(kpis?.totalInputTokens)} />
        <KpiCard label="Tokens de salida" value={formatUnavailable(kpis?.totalOutputTokens)} />
        <KpiCard
          label="Costo estimado (USD)"
          value={formatCost(kpis?.totalEstimatedCostUsd)}
        />
      </section>

      <form className="observability-search" onSubmit={handleSearchSubmit}>
        <input
          type="search"
          name="search"
          placeholder="Buscar por ID de conversación o usuario…"
          aria-label="Buscar"
        />
        <button type="submit">Buscar</button>
      </form>

      <div className="observability-table-scroll">
      <table className="observability-table">
        <thead>
          <tr>
            <th>Conversación</th>
            <th>Usuario</th>
            <th>Actualizado</th>
            <th>Agente</th>
            <th>Estado</th>
            <th>Calidad</th>
            <th>Costo (USD)</th>
            <th>Mensajes</th>
          </tr>
        </thead>
        <tbody>
          {isLoading && (
            <tr>
              <td colSpan={8}>Cargando…</td>
            </tr>
          )}
          {!isLoading && rows.length === 0 && (
            <tr>
              <td colSpan={8}>No hay conversaciones para los filtros seleccionados.</td>
            </tr>
          )}
          {!isLoading &&
            rows.map((row) => (
              <tr key={row.conversationId}>
                <td>
                  <Link to={`/observability/conversations/${encodeURIComponent(row.conversationId)}`}>
                    {row.conversationId.slice(0, 8)}…
                  </Link>
                </td>
                <td>{row.userId}</td>
                <td>{new Date(row.updatedAt).toLocaleString()}</td>
                <td>{row.primaryDomain ?? "No disponible"}</td>
                <td>{row.businessOutcome ?? "No disponible"}</td>
                <td>
                  {row.operationalQualityScore === null
                    ? "No disponible"
                    : `${Math.round(row.operationalQualityScore * 100)}%`}
                </td>
                <td>{formatCost(row.totalEstimatedCostUsd)}</td>
                <td>{row.messageCount ?? "No disponible"}</td>
              </tr>
            ))}
        </tbody>
      </table>
      </div>

      <div className="observability-pagination">
        <button type="button" disabled={skip === 0} onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}>
          Anterior
        </button>
        <span>
          {total === 0 ? "0" : skip + 1}–{Math.min(skip + PAGE_SIZE, total)} de {total}
        </span>
        <button type="button" disabled={skip + PAGE_SIZE >= total} onClick={() => setSkip(skip + PAGE_SIZE)}>
          Siguiente
        </button>
      </div>
    </main>
  );
}

function KpiCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="observability-kpi-card">
      <div className="observability-kpi-card__value">{value}</div>
      <div className="observability-kpi-card__label">{label}</div>
    </div>
  );
}
